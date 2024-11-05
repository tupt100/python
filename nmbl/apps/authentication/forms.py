from authentication.adapters import get_invitations_adapter
from authentication.exceptions import AlreadyAccepted, \
    AlreadyInvited, UserRegisteredEmail
from authentication.models import Invitation, User
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import ugettext_lazy as _


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['email', 'password1', 'password2']


class CleanEmailMixin(object):

    def validate_invitation(self, email):
        if Invitation.objects.all_valid().filter(
                email__iexact=email, accepted=False):
            return True
            # raise AlreadyInvited
        elif Invitation.objects.filter(email__iexact=email, accepted=True):
            raise AlreadyAccepted
        elif get_user_model().objects.filter(email__iexact=email):
            raise UserRegisteredEmail
        else:
            return True

    def clean_email(self):
        email = self.cleaned_data["email"]
        email = get_invitations_adapter().clean_email(email)

        errors = {
            "already_invited": _("This e-mail address has already been"
                                 " invited."),
            "already_accepted": _("This e-mail address has already"
                                  " accepted an invite."),
            "email_in_use": _("An active user is using this e-mail address"),
        }
        try:
            self.validate_invitation(email)
        except(AlreadyInvited):
            return email
            # raise forms.ValidationError(errors["already_invited"])
        except(AlreadyAccepted):
            raise forms.ValidationError(errors["already_accepted"])
        except(UserRegisteredEmail):
            raise forms.ValidationError(errors["email_in_use"])
        return email


class InviteForm(forms.Form, CleanEmailMixin):
    email = forms.EmailField(
        label=_("E-mail"), required=True,
        widget=forms.TextInput(attrs={"type": "email", "size": "30"}
                               ), initial="")

    def save(self, email):
        try:
            inv_obj = Invitation.objects.get(email=email)
            # before deleting take the old data detail
            new_inv_by = inv_obj.invited_by
            new_inv_by_company = inv_obj.invited_by_company
            new_inv_by_group = inv_obj.invited_by_group
            inv_obj.delete()
            return Invitation.create(email=email,
                                     invited_by=new_inv_by,
                                     invited_by_company=new_inv_by_company,
                                     invited_by_group=new_inv_by_group)
        except Exception as e:
            print("exception:", e)
            return Invitation.create(email=email)


class InvitationAdminAddForm(forms.ModelForm, CleanEmailMixin):
    email = forms.EmailField(label=_("E-mail"), required=True,
                             widget=forms.TextInput(
                                 attrs={"type": "email", "size": "30"}))

    def save(self, *args, **kwargs):
        cleaned_data = super(InvitationAdminAddForm, self).clean()
        email = cleaned_data.get("email")
        params = {'email': email}
        if cleaned_data.get("invited_by"):
            params['invited_by'] = cleaned_data.get("invited_by")
        if cleaned_data.get("invited_by_company"):
            params['invited_by_company'] = \
                cleaned_data.get("invited_by_company")
        if cleaned_data.get("invited_by_group"):
            params['invited_by_group'] = \
                cleaned_data.get("invited_by_group")
        instance = Invitation.create(**params)
        instance.send_invitation(self.request)
        instance.invited_by = self.request.user
        instance.save()
        super(InvitationAdminAddForm, self).save(*args, **kwargs)
        return instance

    class Meta:
        model = Invitation
        fields = ("email", "invited_by_company", "invited_by_group")


class InvitationAdminChangeForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = '__all__'
