from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Tag
from django.forms import ModelForm
import re

class NewTagForm(ModelForm):
    class Meta:
       model = Tag
       fields = [ 'tag','owner','description' ]
       help_texts = {
          'description': 'Optional - e.g. something like "my ov card", or "blue fob".',
       }

class TagForm(ModelForm):
    class Meta:
       model = Tag
       fields = [ 'tag', 'description', 'last_used' ]

    def __init__(self, *args, **kwargs):
       self.canedittag = kwargs.pop('canedittag')
       super(TagForm, self).__init__(*args, **kwargs)

       self.fields['last_used'].widget.attrs['readonly'] = True
       if not self.canedittag:
          self.fields['tag'].widget.attrs['readonly'] = True

    def clean_tag(self):
        tag = self.cleaned_data['tag']
        return '-'.join([ b for b in re.compile('[^0-9]+').split(tag.upper()) if b is not None and b is not ''  and int(b) >= 0 and int(b) < 256 ])
