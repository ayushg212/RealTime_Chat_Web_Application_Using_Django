# forms.py

from django import forms
from .models import ChatGroup

class ChatGroupForm(forms.ModelForm):
    class Meta:
        model = ChatGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Group Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Group Description'}),
        }
        labels = {
            'name': 'Group Name',
            'description': 'Group Description',
        }
