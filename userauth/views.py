from django.shortcuts import render,redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from django.contrib.auth.forms import AuthenticationForm

# Create your views here.

def signup_view(request):
    form = CustomUserCreationForm()
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST or None)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    return render(request, 'userauth\signup.html', {'form':form} )

        
def login_view(request):
    form = AuthenticationForm()
    if request.method == 'POST':
        form = AuthenticationForm(data = request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    return render(request, 'userauth\login.html', {'form':form} )
    