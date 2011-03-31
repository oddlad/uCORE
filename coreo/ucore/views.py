"""
  Views provide the views (or the controllers in a MVC applications)
  for the Django project.  This file was created and maintained by:
  Jason Cooper, Jason Hotelling, Paul Coleman, and Paul Boone.
"""

import csv, datetime, json, logging, os, re, time, urllib2, zipfile
from cStringIO import StringIO

from django.core.mail import send_mail
from django.conf import settings
from django.contrib import auth
from django.core import serializers
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson as json

from coreo.ucore.models import *
from coreo.ucore import shapefile, utils


def add_library(request):
  """ 
  Add ``LinkLibrary``s to the user's ``LinkLibrary`` collection (i.e. the ``CoreUser.libraries`` field).
  This view accepts only POST requests. The request's ``library_id`` parameter should contain the
  ``LinkLibrary`` IDs to be added to the user's collection.
  """
  if request.method != 'POST':
    return HttpResponse('Only POST is supported!')

  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  user = CoreUser.objects.get(username=request.user.username)
  library_ids = request.POST.getlist('library_id')

  try:
    for library_id in library_ids:
      user.libraries.add(LinkLibrary.objects.get(pk=library_id))
  except LinkLibrary.DoesNotExist as e:
    return HttpResponse(e.message)

  return HttpResponseRedirect(reverse('coreo.ucore.views.success'))


def create_library(request):
  """
  This view when called will create a link library. It won't work properly unless you are
  already logged in to the webapp in a legitimate way.
 
  Parameters:
    ``links`` - a comma-delimited list of the primary keys of the links you want
                to add to the created link library. They are passed in from
                request object via POST.
    ``name`` -  the name you wish to call the created link library.  Passed in
                from the request object via POST.
    ``desc`` -  The description you want to use for the link library.
    ``tags`` -  Another comma-delimited list of the names of the tags you want
                to associate with the link library you are creating. If the tags
                are not found within the Tag table, they will be created.

  Returns:
    This view should return the same page that called it, which is testgrid.
    We may need to modify this when it is more smoothly integrated into our
    existing webapp.
  """
  user = CoreUser.objects.get(username=request.user)

  if not user:
    logging.error('No user retrieved by the username of %s' % request.user)

    return HttpResponse('No user identified in request.')

  if request.method == 'POST':
    links = request.POST['links'].strip()
    name = request.POST['name'].strip()
    desc = request.POST['desc'].strip()
    tags = request.POST['tags'].strip()

    if tags[-1] == ',':
      length_of_tags = len(tags)
      tags = tags[0:length_of_tags-1]

    linkArray = links.split(',')
    tags = tags.split(',')
    library = LinkLibrary(name=name, desc=desc, creator=user)
    library.save()

    for t in tags:
      t = t.strip()
      retrievedtag = Tag.objects.get_or_create(name=t)
      library.tags.add(retrievedtag[0])

    for link_object in linkArray:
      link = Link.objects.get(pk=int(link_object))
      library.links.add(link)

    library.save()
  # except Exception, e:
  #   print e.message
  #   logging.error(e.message)
  else:
    return HttpResponse('only POST Supported.', status=405)

  return render_to_response('testgrid.html',  context_instance=RequestContext(request))


def create_user(request):
  """
  Create the user's record in the DB.
  """ 
  sid = request.POST['sid'].strip()
  username = request.POST['username'].strip()
  first_name = request.POST['first_name'].strip()
  last_name = request.POST['last_name'].strip()
  password = request.POST['password'].strip()
  email = request.POST['email'].strip()
  phone_number = request.POST['phone_number'].strip()

  try:
    if (len(phone_number) != 10): 
      prog = re.compile(r"\((\d{3})\)(\d{3})-(\d{4})")
      result = prog.match(phone_number)
      phone_number = result.group(1) + result.group(2) + result.group(3)
  except Exception, e:
    logging.error('Exception parsing phone number: %s' % e.message)

  if not (sid and username and first_name and last_name and password and email and phone_number):
    # redisplay the registration page
    return render_to_response('register.html',
        {'sid': sid,
         'error_message': 'Please fill in all required fields.'
        }, context_instance=RequestContext(request))

  # create the user in the DB
  try:
    user = CoreUser.objects.create(sid=sid, username=username, first_name=first_name, last_name=last_name,
                                   email=email, phone_number=phone_number)
  except IntegrityError:
    return render_to_response('register.html',
        {'sid': sid,
         'error_message': 'The username/sid %s is not available. Please try again' % username
        }, context_instance=RequestContext(request))

  user.set_password(password)
  user.save()

  # return an HttpResponseRedirect so that the data can't be POST'd twice if the user hits the back button
  return HttpResponseRedirect(reverse('coreo.ucore.views.login'))


def earn_trophy(request):
  if request.method == 'POST':
    user2 = request.POST['user'].strip()
    trophy2 = request.POST['trophy'].strip()
    trophyc = Trophy.objects.get(pk=trophy2)
    userc = CoreUser.objects.get(username=user2)
    tc = TrophyCase(user=userc, trophy=trophyc, date_earned=datetime.datetime.now())
    tc.save()
    custom_msg = 'You have won a trophy, %s.  Congratulations' % userc.first_name
    user_email = userc.email
    send_mail(custom_msg , 'Testing e-mails', 'trophy@layeredintel.com', [user_email], fail_silently=True)


def ge_index(request):
  # This is a quick hack at getting our Google Earth app integrated with Django.
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  try:
    user = CoreUser.objects.get(username=request.user.username)
  except CoreUser.DoesNotExist:
    # as long as the login_user view forces them to register if they don't already 
    # exist in the db, then we should never actually get here. Still, better safe than sorry.
    return render_to_response('login.html', context_instance=RequestContext(request))
  
  return render_to_response('geindex.html', {'user': user}, context_instance=RequestContext(request))


def gm_index(request):
  # This is a quick hack at getting our Google Maps app integrated with Django.
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  try:
    user = CoreUser.objects.get(username=request.user.username)
  except CoreUser.DoesNotExist:
    # as long as the login_user view forces them to register if they don't already 
    # exist in the db, then we should never actually get here. Still, better safe than sorry.
    return render_to_response('login.html', context_instance=RequestContext(request))
  
  return render_to_response('gmindex.html', {'user': user}, context_instance=RequestContext(request))


def get_csv(request):
  """
  The purpose of this view is to return a csv file that represents the 
  data on a GE view.  As of now, we don't have anything on the client
  side to work with this view.

  Parameters:
    Currently no parameters are passed in, but soon we hope to have JSON
    passed in from the client that represents the data from a GE view.

  Returns: 
    This should return an attachment of type text/csv that will be csv
    from the view.  Right now it returns static data.
  """
  response = HttpResponse(mimetype='text/csv')
  response['Content-Disposition'] = 'attachment; filename=sample.csv'
  # This will eventually handle a json object rather than static data.
  # jsonObj = request.POST['gejson'].strip()
  #  if not (jsonObj)
  # jsonObj = '{["latitude":1.0, "longitude":2.0]}'
  # jsonObj = '["baz":"booz", "tic":"tock"]'
  # obj = json.loads(jsonObj)
  csv_data = (
      ('First', '1', '2', '3'),
      ('Second', '4', '5', '6'),
      ('Third', '7', '8', '9')
  )
  
  writer = csv.writer(response)
  writer.writerow(['First', '1', '2', '3'])
  writer.writerow(['Second', '4', '5', '6'])
  writer.writerow(['Third', '7', '8', '9'])

  return response


def get_kmz(request):
  """
  Return a KMZ file that represents the data from a GE view in our webapp.

  Parameters:
    No parameters have yet been accepted, but eventually the client will
    be submitting a JSON object that represents the data from the GE view
    that we wish to convert to KMZ.

  Returns:
    This view will return a file attachment that is KMZ to the client.
    Right now we return static data. when the user requests /get-kmz/.
  """
  # I must say I used some of : http://djangosnippets.org/snippets/709/
  # for this part. - PRC
  # I know this will be replaced once I have a sample JSON from the client
  # passed in.  For now I am just using sample data provided by Google.
  fileObj = StringIO()
  fileObj.write('<?xml version="1.0" encoding="UTF-8"?>\n')
  fileObj.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
  fileObj.write('<Placemark>\n')
  fileObj.write('<name>Simple placemark</name>\n')
  fileObj.write('<description>Attached to the ground. Intelligently places itself at the height of the underlying terrain.</description>\n')
  fileObj.write('<Point>\n')
  fileObj.write('<coordinates>-122.0822035425683,37.42228990140251,0</coordinates>\n')
  fileObj.write('</Point>\n')
  fileObj.write('</Placemark>\n')
  fileObj.write('</kml>\n')

  kmz = StringIO()
  f = zipfile.ZipFile(kmz, 'w', zipfile.ZIP_DEFLATED)
  f.writestr("doc.kml", fileObj.getvalue())
  f.close()
  response = HttpResponse(mimetype='application/zip')
  response.content = kmz.getvalue()
  kmz.close()
  response['Content-Type'] = 'application/vnd.google-earth.kmz'
  response['Content-Disposition'] = 'attachment; filename=download.kmz'
  response['Content-Description'] = 'a sample kmz file.'
  response['Content-Length'] = str(len(response.content))

  return response 


def get_library(request, username, lib_name):
  # XXX and try/except in case the lib_name doesn't exist
  # ZZZ Not putting the try in unless the author approves.
  # try :
  library = LinkLibrary.objects.get(user__username=username, name=lib_name)
  # except library.DoesNotExist:
  #   return HttpResponse('No library found.')

  doc = utils.build_kml_from_library(library)
  file_path = 'media/kml/' + username + '-' + lib_name + '.kml'
  #xml.dom.ext.PrettyPrint(doc, open(file_path, "w"))

  with open(file_path, 'w') as f:
    # XXX try setting newl=''
    f.write(doc.toprettyxml(indent='  ', encoding='UTF-8'))

  uri = settings.SITE_ROOT + 'site_media/kml/' + username + '-' + lib_name + '.kml'

  return HttpResponse(uri) 


def check_username(request):
  if request.method == 'GET':
    user = request.GET['username'].strip()
    dbCheck = CoreUser.objects.filter(username=user)
    if (dbCheck.count() > 0):
      boolReturn = True;
    else:
      boolReturn = False;
    return HttpResponse(json.dumps(boolReturn))
  else:
    return HttpResponse('index.html') 


def get_shapefile(request):
  w = shapefile.Writer(shapefile.POLYLINE)
  w.line(parts=[[[1,5],[5,5],[5,1],[3,1],[1,1]]])
  w.poly(parts=[[[1,5],[3,1]]], shapeType=shapefile.POLYLINE)
  w.field('FIRST_FLD', 'C', '40')
  w.field('SECOND_FLD', 'C', '40')
  w.record('First', 'Polygon')
  w.save('sample')
  shp = StringIO()
  f = zipfile.ZipFile(shp, 'w', zipfile.ZIP_DEFLATED)
  f.write('sample.shx')
  f.write('sample.dbf')
  f.write('sample.shp')
  f.close()
  response = HttpResponse(mimetype='application/zip')
  response['Content-Disposition'] = 'attachment; filename=sample1.shp'
  response.content = shp.getvalue()
  shp.close()

  return response


def get_tags(request):
  """
  The purpose of this view is to respond to an AJAX call for all
  the public tags in our Tag table.

  Parameters:
    ``term`` - represents the keyboard input of the user while
               waiting for the auto-complete list to be returned.

  Returns:
    This view returns a list of all the public tags that match the
    parameter submitted.
  """           
  if request.method == 'GET':
    term = request.GET['term'].strip()

    if ',' in term:
      termList = term.split(',')
      length_of_list = len(termList)
      term = termList[length_of_list-1].strip()
      # print 'term is- %s -here' % term

  # XXX if the request method is something besides a GET, it'll still execute the next 2 lines of code....
  results = Tag.objects.filter(name__contains=term, type='P')

  return HttpResponse(serializers.serialize('json', results))


def index(request):
  # If the user is authenticated, send them to the application.
  if request.user.is_authenticated():
    return HttpResponseRedirect(reverse('coreo.ucore.views.ge_index'))

  # If the user is not authenticated, show them the main page.
  return render_to_response('index.html', context_instance=RequestContext(request))


def library_demo(request):
  """
  This view exists to demonstrate the ability to select multiple
  links from our search results and then select the ones you want
  to create a link library.

  Returns:
    If the user requesting this view is authenticated already, this
    view will return the HTML page that goes with it : testgrid.html.
    Otherwise, it will take the request and redirect to the login page.
  """
  if not request.user.is_authenticated(): 
    return render_to_response('login.html', context_instance=RequestContext(request))
  else:
    return render_to_response('testgrid.html', context_instance=RequestContext(request))


def login(request):
  if request.method == 'GET':
    return render_to_response('login.html', context_instance=RequestContext(request))
  else:
    # authenticate the user viw username/password
    username = request.POST['username'].strip()
    password = request.POST['password'].strip()

    # check if the user already exists
    if not CoreUser.objects.filter(username__exact=username).exists():
      return render_to_response('register.html', context_instance=RequestContext(request))

    user = auth.authenticate(username=username, password=password)

    # The user has been succesfully authenticated. Send them to the GE app.
    if user:
      auth.login(request, user)
      return HttpResponseRedirect(reverse('coreo.ucore.views.ge_index'))

    return render_to_response('login.html',
          {'error_message': 'Invalid Username/Password Combination'},
           context_instance=RequestContext(request))


def logout(request):
  """
  Log the user out, terminating the session
  """
  if request.user.is_authenticated():
    auth.logout(request)

  return HttpResponseRedirect(reverse('coreo.ucore.views.index'))


def map_view(request):
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  try:
    user = CoreUser.objects.get(username=request.user.username)
  except CoreUser.DoesNotExist:
    # as long as the login_user view forces them to register if they don't already 
    # exist in the db, then we should never actually get here. Still, better safe than sorry.
    return render_to_response('login.html', context_instance=RequestContext(request))
  
  return render_to_response('map.html', {'user': user}, context_instance=RequestContext(request))


def modify_settings(request):
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  user = get_object_or_404(CoreUser, username=request.user.username)

  if request.method == 'GET':   
    return render_to_response('settings.html', {'settings': user.settings, 'skin_list': Skin.objects.all()},
        context_instance=RequestContext(request))
  elif request.method == 'POST':
    wants_emails = True if 'wants_emails' in request.POST else False
    skin = Skin.objects.get(name=request.POST['skin'].strip())

    user.settings.wants_emails = wants_emails
    user.settings.skin = skin
    user.settings.save()

    return HttpResponseRedirect(reverse('coreo.ucore.views.modify_settings'))


def notifytest(request):
  if not request.user.is_authenticated():
    logging.warning('%s was not authenticated' % request.user)
    return render_to_response('login.html', context_instance=RequestContext(request))

  # user = CoreUser.objects.filter(username=request.user)
  return render_to_response('notify.html', context_instance=RequestContext(request))


def poll_notifications(request, notification_id):
  """
  poll_notifications has two methods it supports: GET and DELETE.
  For DELETE you have to submit a ``notification_id``, which will then
  delete the notification from the DB. 

  If you call a GET, don't send any parameters and the view will
  return a JSON list of all notifications for the logged-in user.
  """ 
  # notification_id is passed in on a delete request in the URL.
  if not request.user.is_authenticated(): 
    return render_to_response('login.html', context_instance=RequestContext(request))

  user = CoreUser.objects.filter(username=request.user)

  if not user: 
    logging.debug('No user retrieved by the username of %s' % request.user)
  response = HttpResponse(mimetype='application/json')

  if request.method == "GET":
    # print 'request user is %s' % request.user
    try:
      json_serializer = serializers.get_serializer('json')()
      notify_list = Notification.objects.filter(user=user)
      json_serializer.serialize(notify_list, ensure_ascii=False, stream=response)
    except Exception, e:
      logging.error(e.message)
      print e.message 

    return response
  elif request.method == "DELETE":
    primaryKey = notification_id 
    logging.debug('Received the following id to delete from notifications : %s' % primaryKey)
    record2delete = Notification.objects.filter(user=user, pk=primaryKey)
    record2delete.delete()

    return response


def rate(request, ratee, ratee_id):
  """
  Rate either a ``Link`` or ``LinkLibrary``.

  Parameters:
    ``ratee`` - a string, whose value must be either 'link' or 'library'. The value of ``ratee`` is
                guaranteed by the app's URL conf file.
    ``ratee_id`` - the ID of the ``Link`` or ``LinkLibrary`` to be rated

  Returns:
    a JSON object. For GET requests, the JSON object represent the ``Link`` or ``LinkLibrary`` and the
    related ``Rating``, if one already exists. For POST requests, the JSON object is simply the new
    ``Rating`` instance resulting for updating the database.
  """ 
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  user = get_object_or_404(CoreUser, username=request.user.username)
  link = get_object_or_404(Link, pk=ratee_id) if ratee == 'link' else None
  link_library = get_object_or_404(LinkLibrary, pk=ratee_id) if ratee == 'library' else None

  # check to see if a RatingFK already exists for this (CoreUser, (Link|LinkLibrary)) combo. If the combo already exists:
  #   1. and this is a GET, pass the Rating to the template to be rendered so the user can update the Rating
  #   2. and this is a POST, update the Rating
  try:
    rating_fk = RatingFK.objects.get(user=user, link=link, link_library=link_library)
  except RatingFK.DoesNotExist:
    rating_fk = None

  if rating_fk:
    try:
      rating = Rating.objects.get(rating_fk=rating_fk)
    except Rating.DoesNotExist:
      if not rating: raise IntegrityError('A RatingFK %s exists, but is not associated with a Rating' % rating_fk)

  if request.method == 'GET':
    if rating_fk:
      context = {'rating': utils.django_to_dict(rating), 'link': utils.django_to_dict(link),
                 'link_library': utils.django_to_dict(link_library)}
    else:
      context = {'link': utils.django_to_dict(link), 'link_library': utils.django_to_dict(link_library)}

    return HttpResponse(json.dumps(context))
  elif request.method == 'POST':
    if rating_fk:
      rating.score, rating.comment = (request.POST['score'], request.POST['comment'].strip())
      rating.save()
    else:
      if ratee == 'link': rating_fk = RatingFK.objects.create(user=user, link=link)
      elif ratee == 'library': rating_fk = RatingFK.objects.create(user=user, link_library=link_library)

      rating = Rating.objects.create(rating_fk=rating_fk, score=request.POST['score'], comment=request.POST['comment'].strip())

    return HttpResponse(json.dumps(utils.django_to_dict(rating)))
  else:
    return HttpResponse('%s is not a supported method' % request.method, status=405)


def register(request, sid):
  """
  Pull out the user's sid, name, email, and phone number from the user's certs.
  Return a pre-filled registration form with this info so the user can create an account.
  """
  # get the sid and name from the cert
  #name_sid = os.getenv('SSL_CLIENT_S_DN_CN', '').split(' ')
  #name = ' '.join(name_sid[:-1])
  #sid = name_sid[-1]

  # XXX in the future we'll be returning more info (sid, name, email, phone number).
  # The user will basically just need to verify the info and put in some basic additional
  # info (main areas of interest, skin, etc).
  return render_to_response('register.html', {'sid': sid}, context_instance=RequestContext(request))


def search(request, models):
  """
  Search the databases for ``Links`` or ``LinkLibraries`` whose metadata matches the search terms. The
  metadata searched is the name, description, and tag names associated with the ``Link`` or ``LinkLibrary``.
  The search terms come from the POST parameter ``q``, which should be a comma-separated list of strings.

  Parameters:
    ``models`` - a sequence of strings specifying the models to search. Must be a combination of
                 'Link' or 'LinkLibrary'. The values are guaranteed by the app's URL conf file.

  Returns:
    a JSON object containing the matching ``Links`` and/or ``LinkLibraries``.
  """
  if not request.GET['q']:
    return HttpResponse(serializers.serialize('json', ''))

  terms = request.GET['q'].split(',') 

  # if the only search term is '*', then search everything
  if len(terms) == 1 and terms[0] == '*': terms[0] = ''

  results = utils.search_ucore(models, terms)

  return HttpResponse(serializers.serialize('json', results, use_natural_keys=True))


def search_mongo(request):
  url = 'http://174.129.206.221/hello//?' + request.GET['q']
  result = urllib2.urlopen(url)

  return HttpResponse('\n'.join(result.readlines()))


def success(request, message=''):
  return HttpResponse('you did it!')


def trophy_room(request):
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  try: 
    user = CoreUser.objects.get(username=request.user.username)
    trophy_list = Trophy.objects.all()
    trophy_case_list = TrophyCase.objects.all()
    earn_total = []
    earn_progress = []
    percentage = []
    for i in trophy_list:
      earn_total += [i.earning_req]
    # print 'total elements in list: ', earn_total  
    for t in trophy_list:
      for o in trophy_case_list:
        if (o.trophy == t):
          # print 'Found one : %s' % t.name
          if o.date_earned:
            earn_progress += [t.earning_req]
            percentage += [(o.count / t.earning_req)*100]
          else:
            earn_progress += [o.count]
            percentage += [(o.count / t.earning_req)*100]
        else:
          earn_progress += [0]
          percentage += [(o.count / t.earning_req)*100]
    # print 'total earn_progress looks like: ', earn_progress        
    combine_list = zip(trophy_list, earn_progress, percentage)
  except CoreUser.DoesNotExist: 
    # as long as the login_user view forces them to register if they don't already 
    # exist in the db, then we should never actually get here. Still, better safe than sorry.
    return render_to_response('login.html', context_instance=RequestContext(request))
  return render_to_response('trophyroom.html',
      {'trophy_list' : combine_list,
       'trophy_case_list' : trophy_case_list,
       'user' : user.username,
       'earn_total' : earn_total,
       'earn_progress' : earn_progress,
       }, context_instance=RequestContext(request))


def test_chart(request):
   return render_to_response('chart.html', context_instance=RequestContext(request))


def update_user(request):
  """
  Update the user's record in the DB.
  """ 
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  first_name = request.POST['first_name'].strip()
  last_name = request.POST['last_name'].strip()
  password = request.POST['password'].strip()
  email = request.POST['email'].strip()
  phone_number = request.POST['phone_number'].strip()

  try:
    if (len(phone_number) != 10): 
      prog = re.compile(r"\((\d{3})\)(\d{3})-(\d{4})")
      result = prog.match(phone_number)
      phone_number = result.group(1) + result.group(2) + result.group(3)
  except Exception, e:
    logging.error('Exception parsing phone number: %s' % e.message)

  if not (first_name and last_name and password and email and phone_number):
    # redisplay the registration page
    return render_to_response('register.html',
        {'sid': sid,
         'error_message': 'Please fill in all required fields.'
        }, context_instance=RequestContext(request))

  # update the user to the DB
  user = CoreUser.objects.get(sid=sid)
  user.first_name = first_name
  user.last_name = last_name
  user.email = email
  user.phone_number = phone_number 
  user.set_password(password)
  user.save()

  # return an HttpResponseRedirect so that the data can't be POST'd twice if the user hits the back button
  # XXX should have a success msg when we redirect or the client call is ajax and we return "sucess" that way
  return HttpResponseRedirect(reverse('coreo.ucore.views.user_profile'))


def upload_csv(request):
  if request.method == 'POST':
    utils.insert_links_from_csv(request.FILES['file'])
      
  return render_to_response('upload_csv.html', context_instance=RequestContext(request))


def user_profile(request):
  #XXX the django dev server can't use ssl, so fake getting the sid from the cert
  #XXX pull out the name as well. pass it to register() and keep things DRY
  #sid = os.getenv('SSL_CLIENT_S_DN_CN', '').split(' ')[-1]
  #sid = 'jlcoope'
  #if not sid: return render_to_response('install_certs.html')
  if not request.user.is_authenticated():
    return render_to_response('login.html', context_instance=RequestContext(request))

  try:
    user = CoreUser.objects.get(username=request.user.username)
  except CoreUser.DoesNotExist:
    # as long as the login_user view forces them to register if they
    # don't already exist in the db, then we should never actually get here.
    # Still, better safe than sorry.
    return render_to_response('login.html', context_instance=RequestContext(request))
  
  return render_to_response('userprofile.html', {'user': user}, context_instance=RequestContext(request))

