from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from .models import User, UserProfile, Client, Case, CaseEvent, EventType, CaseDocument, DocumentVersion
from django.utils import timezone

class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
            # Create profile automatically
            UserProfile.objects.create(user=user)
        return user

class UserLoginForm(AuthenticationForm):
    remember_me = forms.BooleanField(required=False, widget=forms.CheckboxInput())

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['bio', 'profile_picture', 'phone', 'address']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['full_name', 'email', 'phone', 'address', 'organization']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'organization': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ['title', 'description', 'client', 'assigned_to', 'case_type', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'case_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter assigned_to to only lawyers and paralegals
        self.fields['assigned_to'].queryset = User.objects.filter(role__in=['lawyer', 'paralegal'])

# EVENT FORMS
class EventForm(forms.ModelForm):
    class Meta:
        model = CaseEvent
        fields = [
            'title', 'description', 'event_type', 'priority', 'starts_at', 'ends_at', 
            'is_all_day', 'location', 'attendees', 'reminder_minutes', 'is_deadline'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'starts_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'ends_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'is_all_day': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'attendees': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '4'}),
            'reminder_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_deadline': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        case = kwargs.pop('case', None)
        super().__init__(*args, **kwargs)
        
        # Filter attendees to lawyers and paralegals
        self.fields['attendees'].queryset = User.objects.filter(role__in=['lawyer', 'paralegal'])
        
        # Set default values
        if not self.instance.pk:  # New event
            self.fields['starts_at'].initial = timezone.now().replace(second=0, microsecond=0)
            
        # If we have a case, we could set defaults based on case
        if case:
            if case.assigned_to:
                self.fields['attendees'].initial = [case.assigned_to]

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')
        is_all_day = cleaned_data.get('is_all_day')
        
        if starts_at and ends_at and not is_all_day:
            if starts_at >= ends_at:
                raise forms.ValidationError("Ora e fillimit duhet të jetë para orës së mbarimit.")
        
        return cleaned_data

class EventFilterForm(forms.Form):
    start_date = forms.DateField(
        required=False, 
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False, 
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    event_type = forms.ModelChoiceField(
        queryset=EventType.objects.all(), 
        required=False,
        empty_label="Të gjitha llojet",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        choices=[('', 'Të gjitha prioritetet')] + CaseEvent.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['lawyer', 'paralegal']),
        required=False,
        empty_label="Të gjithë",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_deadline = forms.BooleanField(
        required=False,
        label="Vetëm afatet",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class QuickEventForm(forms.ModelForm):
    """Simplified form for quick event creation"""
    class Meta:
        model = CaseEvent
        fields = ['title', 'starts_at', 'event_type', 'is_deadline']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titulli i eventit...'}),
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'is_deadline': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# DOCUMENT MANAGEMENT FORMS
class DocumentUploadForm(forms.ModelForm):
    """Form for uploading new documents"""
    
    class Meta:
        model = CaseDocument
        fields = ['title', 'description', 'file', 'doc_type', 'status', 'is_confidential']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter document title...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description...'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.zip'
            }),
            'doc_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_confidential': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        case = kwargs.pop('case', None)
        super().__init__(*args, **kwargs)
        
        # Add file size validation message
        self.fields['file'].help_text = 'Maximum file size: 50MB. Supported formats: PDF, Word, Excel, PowerPoint, Text, Images, ZIP'
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (50MB limit)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size cannot exceed 50MB.')
            
            # Check file extension
            allowed_extensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'jpeg', 'png', 'zip']
            file_extension = file.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(f'File type .{file_extension} is not supported.')
        
        return file

class DocumentUpdateForm(forms.ModelForm):
    """Form for updating document metadata (not the file itself)"""
    
    class Meta:
        model = CaseDocument
        fields = ['title', 'description', 'doc_type', 'status', 'is_confidential']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'doc_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_confidential': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class DocumentVersionForm(forms.ModelForm):
    """Form for uploading new version of existing document"""
    
    class Meta:
        model = DocumentVersion
        fields = ['file', 'change_notes']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png,.zip'
            }),
            'change_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the changes made in this version...'
            }),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size cannot exceed 50MB.')
        return file

class DocumentSearchForm(forms.Form):
    """Form for searching and filtering documents"""
    
    search = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search documents...'
        })
    )
    
    doc_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + CaseDocument.DOCUMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status')] + CaseDocument.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    case = forms.ModelChoiceField(
        queryset=Case.objects.all(),
        required=False,
        empty_label="All Cases",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    uploaded_by = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['lawyer', 'paralegal', 'admin']),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    confidential_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
