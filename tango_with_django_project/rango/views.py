from django.template import RequestContext
from django.shortcuts import render_to_response
from rango.models import Category, Page
from rango.forms import CategoryForm, PageForm, UserForm, UserProfileForm
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from datetime import datetime
from rango.bing_search import run_query

def get_category_list():
    cat_list = Category.objects.all()

    for cat in cat_list:
        cat.url = encode_url(cat.name)

    return cat_list

def encode_url(str):
	return str.replace(' ', '_')

def decode_url(str):
	return str.replace('_', ' ')

def index(request):
	context = RequestContext(request)

	cat_list = get_category_list() #sidebar

	# top 5 categories and pages by view
	top_categories = Category.objects.order_by('-views')[:5]
	for cat in top_categories:
		cat.url = encode_url(cat.name)
	page_list = Page.objects.order_by('-views')[:5]

	context_dict = {"cat_list":cat_list, "pages": page_list, "categories":top_categories}

	if request.session.get('last_visit'):
	    # The session has a value for the last visit
	    last_visit_time = request.session.get('last_visit')
	    visits = request.session.get('visits', 0)

	    if (datetime.now() - datetime.strptime(last_visit_time[:-7], "%Y-%m-%d %H:%M:%S")).days > 0:
	        request.session['visits'] = visits + 1
	        request.session['last_visit'] = str(datetime.now())
	else:
	    # The get returns None, and the session does not have a value for the last visit.
	    request.session['last_visit'] = str(datetime.now())
	    request.session['visits'] = 1

	# Render and return the rendered response back to the user.
	return render_to_response('rango/index.html', context_dict, context)

def about(request):
	context = RequestContext(request)
	context_dict = {'thing': "awesome application for food"}
	if request.session.get('visits'):
		count = request.session.get('visits')
	else:
		count = 0
	context_dict['visits'] = count

	cat_list = get_category_list()
	context_dict['cat_list'] = cat_list

	return render_to_response('rango/about.html', context_dict, context)

def category(request, category_name_url):
    # Request our context
    context = RequestContext(request)

    # Change underscores in the category name to spaces.
    # URL's don't handle spaces well, so we encode them as underscores.
    category_name = decode_url(category_name_url)

    # Build up the dictionary we will use as out template context dictionary.
    context_dict = {'category_name': category_name, 'category_name_url': category_name_url}

    cat_list = get_category_list()
    context_dict['cat_list'] = cat_list

    try:
        # Find the category with the given name.
        # Raises an exception if the category doesn't exist.
        # We also do a case insensitive match.
        category = Category.objects.get(name__iexact=category_name)
        context_dict['category'] = category
        # Retrieve all the associated pages.
        # Note that filter returns >= 1 model instance.
        pages = Page.objects.filter(category=category).order_by('-views')

        # Adds our results list to the template context under name pages.
        context_dict['pages'] = pages
    except Category.DoesNotExist:
        # We get here if the category does not exist.
        # Will trigger the template to display the 'no category' message.
        pass

    if request.method == 'POST':
      	query = request.POST.get('query')
        if query:
      		query = query.strip()
        	result_list = run_query(query)
        	context_dict['result_list'] = result_list

    # Go render the response and return it to the client.
    return render_to_response('rango/category.html', context_dict, context)

@login_required
def add_category(request):
	context = RequestContext(request)
	cat_list = get_category_list()

	if request.method == 'POST':
		form = CategoryForm(request.POST)

		if form.is_valid():
			form.save(commit=True)

			return index(request)
		else: 
			print form.errors
	else:
		form = CategoryForm()

	return render_to_response('rango/add_category.html', {'form':form, 'cat_list': cat_list}, context)

@login_required
def add_page(request, category_name_url):
    context = RequestContext(request)

    category_name = decode_url(category_name_url)
    if request.method == 'POST':
        form = PageForm(request.POST)

        if form.is_valid():
            # This time we cannot commit straight away.
            # Not all fields are automatically populated!
            page = form.save(commit=False)

            # Retrieve the associated Category object so we can add it.
            # Wrap the code in a try block - check if the category actually exists!
            try:
                cat = Category.objects.get(name=category_name)
                page.category = cat
            except Category.DoesNotExist:
                # If we get here, the category does not exist.
                # Go back and render the add category form as a way of saying the category does not exist.
                return render_to_response('rango/add_category.html', {}, context)

            # Also, create a default value for the number of views.
            page.views = 0

            # With this, we can then save our new model instance.
            page.save()

            # Now that the page is saved, display the category instead.
            return category(request, category_name_url)
        else:
            print form.errors
    else:
        form = PageForm()

    cat_list = get_category_list()
    context_dict = {'category_name_url': category_name_url,
             'category_name': category_name, 'form': form, "cat_list":cat_list}
    return render_to_response( 'rango/add_page.html',
            context_dict, context)

def register(request):
	context = RequestContext(request)

	registered = False

	if request.method == "POST":
		user_form = UserForm(data=request.POST)
		profile_form = UserProfileForm(data=request.POST)

		if user_form.is_valid() and profile_form.is_valid():
			user = user_form.save()

			user.set_password(user.password)
			user.save()

			profile = profile_form.save(commit=False)
			profile.user = user

			#checks if picture is uploaded or not
			if 'picture' in request.FILES:
				profile.picture = request.FILES['picture']

			profile.save()

			registered=True
		else:
			print user_form.errors, profile_form.errors

	else:
		user_form = UserForm()
		profile_form = UserProfileForm()

	context_dict = {'user_form':user_form, 'profile_form':profile_form, 'registered': registered}
	cat_list = get_category_list()
	context_dict['cat_list'] = cat_list
	return render_to_response('rango/register.html', context_dict, context)

def user_login(request):
	context = RequestContext(request)
	cat_list = get_category_list()

	if request.method == "POST":
		username = request.POST['username']
		password = request.POST['password']

		user = authenticate(username=username, password=password)

		if user: #authentication success
			if user.is_active:
				login(request, user)
				return HttpResponseRedirect('/rango/')
			else:
				return HttpResponse("Your Rango Account is disabled.")
		else:
			print "Invalid Login Details: {0}, {1}".format(username, password)
			return HttpResponse("Invalid login details supplied.")

	else:
		return render_to_response('rango/login.html', {"cat_list":cat_list}, context)

@login_required
def user_logout(request):
	logout(request)
	return HttpResponseRedirect('/rango/')

@login_required
def restricted(request):
	context = RequestContext(request)
	cat_list=get_category_list()
	return render_to_response('rango/restricted.html', {'cat_list':cat_list}, context)

def search(request):
    context = RequestContext(request)
    result_list = []

    if request.method == 'POST':
        query = request.POST['query'].strip()

        if query:
            # Run our Bing function to get the results list!
            result_list = run_query(query)
    cat_list = get_category_list()
    return render_to_response('rango/search.html', {'result_list': result_list, 'cat_list':cat_list}, context)



