from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import User, UserProfile, UserAuditLog

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile when a new User is created.
    """
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save the UserProfile when the User is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log user login events.
    """
    UserAuditLog.objects.create(
        user=user,
        action='login',
        ip_address=request.META.get('REMOTE_ADDR'),
        metadata={
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'session_key': request.session.session_key
        }
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Log user logout events.
    """
    if user:
        UserAuditLog.objects.create(
            user=user,
            action='logout',
            ip_address=request.META.get('REMOTE_ADDR'),
            metadata={
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'session_key': getattr(request.session, 'session_key', None)
            }
        )
