# forms_improved.py - Forms për sistemin e përmirësuar
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models_improved import (
    User, Client, Case, Document, DocumentCategory, DocumentType,
    DocumentStatus, DocumentCaseRelation, DocumentAccess
)

# ==========================================
# USER FORMS
# ==========================================

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_2fa_enabled')

# ==========================================
# CLIENT FORMS
# ==========================================

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['full_name', 'email', 'phone', 'address', 'organization']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Emri i plotë'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Telefon'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresa'}),
            'organization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Organizata (opsionale)'}),
        }

class ClientSearchForm(forms.Form):
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kërko sipas emrit, email-it ose organizatës...'
        })
    )

# ==========================================
# CASE FORMS
# ==========================================

class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ['title', 'description', 'client', 'assigned_to', 'case_type', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titulli i rastit'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Përshkrimi i rastit'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'case_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtro assigned_to për të përfshirë vetëm lawyer dhe paralegal
        self.fields['assigned_to'].queryset = User.objects.filter(
            role__in=['lawyer', 'paralegal']
        )
        
        # Nëse user nuk është admin, limito opsionet
        if user and user.role != 'admin':
            self.fields['assigned_to'].queryset = self.fields['assigned_to'].queryset.filter(
                id=user.id
            )

class CaseFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'Të gjitha')] + Case.STATUS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    case_type = forms.ChoiceField(
        choices=[('', 'Të gjitha')] + Case.CASE_TYPE,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['lawyer', 'paralegal']),
        required=False,
        empty_label="Të gjithë avokatët",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kërko sipas titullit, UID, ose përshkrimit...'
        })
    )

# ==========================================
# DOCUMENT FORMS
# ==========================================

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'title', 'description', 'file', 'document_type', 'status',
            'is_template', 'template_variables', 'tags', 'is_confidential', 'access_level'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titulli i dokumentit'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Përshkrimi'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tags të ndarë me virgulë'}),
            'is_template': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_confidential': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
            'template_variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'JSON format për template variables'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Grupo document types sipas kategorive
        self.fields['document_type'].queryset = DocumentType.objects.select_related('category')

class DocumentFilterForm(forms.Form):
    document_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.select_related('category'),
        required=False,
        empty_label="Të gjitha tipet",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ModelChoiceField(
        queryset=DocumentStatus.objects.all(),
        required=False,
        empty_label="Të gjitha statuset",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    access_level = forms.ChoiceField(
        choices=[('', 'Të gjitha')] + Document._meta.get_field('access_level').choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_template = forms.ChoiceField(
        choices=[('', 'Të gjitha'), ('true', 'Vetëm Templates'), ('false', 'Jo Templates')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    case = forms.ModelChoiceField(
        queryset=Case.objects.all(),
        required=False,
        empty_label="Të gjitha rastet",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kërko sipas titullit, përshkrimit, ose tags...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtro cases bazuar në user role
        if user:
            if user.role == 'client':
                self.fields['case'].queryset = Case.objects.filter(client__user=user)
            elif user.role in ['lawyer', 'paralegal']:
                self.fields['case'].queryset = Case.objects.filter(assigned_to=user)

class DocumentCaseRelationForm(forms.ModelForm):
    class Meta:
        model = DocumentCaseRelation
        fields = ['case', 'relationship_type', 'notes']
        widgets = {
            'case': forms.Select(attrs={'class': 'form-select'}),
            'relationship_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Shënime opsionale'}),
        }

class DocumentAccessForm(forms.ModelForm):
    class Meta:
        model = DocumentAccess
        fields = [
            'user', 'role', 'can_view', 'can_download', 'can_edit', 'can_delete', 'can_share', 'expires_at'
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'can_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_download': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_share': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Bëj që vetëm një nga user ose role të jetë i kërkuar
        self.fields['user'].required = False
        self.fields['role'].required = False
        
        # Filtro users për të hequr admins nga lista
        self.fields['user'].queryset = User.objects.exclude(role='admin')
    
    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        role = cleaned_data.get('role')
        
        if not user and not role:
            raise forms.ValidationError("Duhet të specifikosh ose user ose role.")
        
        if user and role:
            raise forms.ValidationError("Nuk mund të specifikosh edhe user edhe role.")
        
        return cleaned_data

class DocumentBulkActionForm(forms.Form):
    ACTION_CHOICES = [
        ('delete', 'Fshij'),
        ('change_status', 'Ndrysho statusin'),
        ('change_access_level', 'Ndrysho nivelin e aksesit'),
        ('add_to_case', 'Shto në rast'),
        ('remove_from_case', 'Hiq nga rasti'),
    ]
    
    documents = forms.CharField(widget=forms.HiddenInput())  # JSON list of document IDs
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Optional fields based on action
    new_status = forms.ModelChoiceField(
        queryset=DocumentStatus.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    access_level = forms.ChoiceField(
        choices=Document._meta.get_field('access_level').choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    case = forms.ModelChoiceField(
        queryset=Case.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    relationship_type = forms.ChoiceField(
        choices=DocumentCaseRelation._meta.get_field('relationship_type').choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class DocumentFromTemplateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=Document.objects.filter(is_template=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titulli i dokumentit të ri'})
    )
    case = forms.ModelChoiceField(
        queryset=Case.objects.all(),
        required=False,
        empty_label="Opsionale - Lidh me rast",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    template_variables = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'JSON format për zëvendësimin e variablave në template'
        })
    )
    
    def clean_template_variables(self):
        data = self.cleaned_data['template_variables']
        if data:
            try:
                import json
                json.loads(data)
                return data
            except json.JSONDecodeError:
                raise forms.ValidationError("Template variables duhet të jenë në format JSON të vlefshëm.")
        return data

# ==========================================
# CONFIGURATION FORMS
# ==========================================

class DocumentCategoryForm(forms.ModelForm):
    class Meta:
        model = DocumentCategory
        fields = ['name', 'description', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'category', 'is_template']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'is_template': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class DocumentStatusForm(forms.ModelForm):
    class Meta:
        model = DocumentStatus
        fields = ['name', 'color', 'is_final']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'is_final': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
