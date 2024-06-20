from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required
def home_view(request):
    context = {
        'user': request.user,
        'full_url': request.build_absolute_uri(),
        'user_cookie' : request.COOKIES.get('user_cookies'),
        
    }
    return render(request, 'chatapp\home.html', context )