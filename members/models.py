from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from simple_history.models import HistoricalRecords
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse_lazy,reverse
from stdimage.models import StdImageField
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import RegexValidator
from django import forms

import logging
logger = logging.getLogger(__name__)

from django.db.models.signals import pre_delete, pre_save
# from stdimage.utils import pre_delete_delete_callback, pre_save_delete_callback

from makerspaceleiden.utils import upload_to_pattern

import re, datetime

GDPR_ESCALATED_TIMESPAN_SECONDS = 60 * 10

if hasattr(settings,'GDPR_ESCALATED_TIMESPAN_SECONDS'):
    GDPR_ESCALATED_TIMESPAN_SECONDS = settings.GDPR_ESCALATED_TIMESPAN_SECONDS

class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)

class AuditRecord(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    action = models.TextField(max_length=400)
    recorded = models.DateTimeField(auto_now_add=True, db_index=True)
    final = models.BooleanField(default = False)

    history = HistoricalRecords()

    def __str__(self):
        return f'{self.action} by {self.user} on {self.recorded}'

    def last(user):
       try:
          rec = AuditRecord.objects.all().filter(user = user).latest('recorded')
          if rec.final:
             return None
          return rec.recorded
       except ObjectDoesNotExist:
          return None

class User(AbstractUser):
    class Meta:
        ordering = ['first_name', 'last_name']

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'telegram_user_id']

    username = None

    email = models.EmailField(_('email address'), unique=True)
    phone_regex = RegexValidator(regex=r'^\+\d{9,15}$', message="Phone number must be entered with country code (+31, etc.) and no spaces, dashes, etc.")
    phone_number = models.CharField(validators=[phone_regex], max_length=40, blank=True, null=True, help_text="Optional; only visible to the trustees and board delegated administrators")
    image = StdImageField(upload_to=upload_to_pattern, variations=settings.IMG_VARIATIONS, validators=settings.IMG_VALIDATORS, blank=True, default='',delete_orphans=True)
    form_on_file = models.BooleanField(default=False)
    email_confirmed = models.BooleanField(default=False)
    telegram_user_id = models.CharField(max_length=200, blank=True, null=True, help_text="Optional; Telegram User ID; only visible to the trustees and board delegated administrators")
    uses_signal = models.BooleanField(default=False)
    always_uses_email = models.BooleanField(default=False, help_text="Receive notifications via email even when using a chat BOT")

    history = HistoricalRecords()
    objects = UserManager()

    def __str__(self):
        return '{} {}'.format(self.first_name, self.last_name)

    def name(self):
        return self.__str__()

    def path(self):
        return  reverse('overview', kwargs = { 'member_id' :  self.id })

    def url(self):
        return  settings.BASE + self.path()

    def image_img(self):
         if self.image:
             return str('<img src="%s" width=80/>' % self.image.url)
         else:
             return "No images uploaded yet."

    @property
    def is_privileged(self):
        if self.is_superuser:
           return True

        if not self.is_staff:
           logger.debug("Rejected is_priv, not staff for {}".format(self.name));
           return False

        last = AuditRecord.last(self)

        if last == None:
           logger.debug("Rejected is_priv, no recent audit for {}".format(self.name));
           return False

        endtime =  last +  datetime.timedelta(seconds=GDPR_ESCALATED_TIMESPAN_SECONDS)
        now = datetime.datetime.now(last.tzinfo)

        if endtime > now:
            return True

        logger.debug("Rejected is_priv, last sudo too long ago for {}".format(self.name));
        return False

    @property
    def can_escalate_to_priveleged(self):
        return self.is_staff or self.is_superuser

    def escalate_to_priveleged(self, request, action):
        ar = AuditRecord(user = self, action = action)

class Tag(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    tag = models.CharField(max_length=30, unique=True) #, editable = False)
    description = models.CharField(max_length=300, blank=True, null=True)

    last_used = models.DateTimeField(blank=True, null = True) # , editable = False)

    history = HistoricalRecords()

    def __str__(self):
        return self.tag + ' (' + str(self.owner) + ')'

def clean_tag_string(tag):
    try:
       bts = [ b for b in re.compile('[^0-9]+').split(tag.upper())
                   if b is not None and str(b) != '' and int(b) >=0 and int(b) < 256]
       if len(bts) < 3:
           return None
       return '-'.join(bts)

    except ValueError as e:
       pass

    return None

# Handle image cleanup.
# pre_delete.connect(pre_delete_delete_callback, sender=User)
# pre_save.connect(pre_save_delete_callback, sender=User)
