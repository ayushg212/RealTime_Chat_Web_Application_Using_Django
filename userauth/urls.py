from django.urls import path,include
from .views import signup_view,login_view,custom_logout_view
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('signup/', signup_view, name= 'signup'),
    path('login/', login_view, name= 'login'),
    path('logout/', custom_logout_view, name = 'logout'),
    path('', include('django.contrib.auth.urls')),
]
