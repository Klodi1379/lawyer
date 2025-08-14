from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import models
from datetime import date, timedelta
import json

from .models import Case, Client
from .models_billing import AdvancedInvoice, Payment, Currency, Expense, ExpenseCategory

class BillingDashboardView(LoginRequiredMixin, TemplateView):
    """Billing Dashboard View"""
    template_name = 'billing/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Billing Dashboard',
            'breadcrumbs': [
                {'name': 'Dashboard', 'url': '/'},
                {'name': 'Billing', 'url': None}
            ]
        })
        return context

@login_required
def billing_dashboard(request):
    """Simple function-based view for billing dashboard"""
    return render(request, 'billing/dashboard.html', {
        'page_title': 'Billing Dashboard'
    })

class InvoicesListView(LoginRequiredMixin, ListView):
    """List all invoices with filtering and pagination"""
    model = AdvancedInvoice
    template_name = 'billing/invoices_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AdvancedInvoice.objects.select_related('client', 'case', 'currency')
        
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-issue_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate stats for the cards
        invoices = AdvancedInvoice.objects.all()
        context.update({
            'paid_count': invoices.filter(status='paid').count(),
            'pending_count': invoices.filter(status='sent').count(),
            'overdue_count': invoices.filter(status='overdue').count(),
            'page_title': 'Invoices Management'
        })
        return context

class GenerateInvoiceView(LoginRequiredMixin, CreateView):
    """Generate new invoice"""
    model = AdvancedInvoice
    template_name = 'billing/generate_invoice.html'
    fields = ['client', 'case', 'invoice_number', 'issue_date', 'due_date', 
              'currency', 'payment_terms', 'description']
    success_url = reverse_lazy('invoices_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get suggested invoice number
        last_invoice = AdvancedInvoice.objects.order_by('-id').first()
        suggested_number = 1 if not last_invoice else (int(last_invoice.invoice_number.split('-')[-1]) + 1 if '-' in last_invoice.invoice_number else last_invoice.id + 1)
        
        context.update({
            'clients': Client.objects.all(),
            'cases': Case.objects.select_related('client'),
            'currencies': Currency.objects.all(),
            'suggested_number': f"{suggested_number:04d}",
            'today': date.today().isoformat(),
            'page_title': 'Generate Invoice'
        })
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # Handle invoice items from POST data
        response = super().form_valid(form)
        
        # Process invoice items - this is handled by the model's calculate_totals method
        # For now, we'll add a simple note about the items in the invoice notes
        items_data = self._extract_invoice_items()
        if items_data:
            notes_lines = []
            for item_data in items_data:
                notes_lines.append(f"{item_data['description']}: {item_data['quantity']} x {item_data['rate']} = {item_data['amount']}")
            self.object.notes = "\n".join(notes_lines)
            self.object.save()
        
        # Calculate totals
        self.object.calculate_totals()
        
        messages.success(self.request, 'Invoice generated successfully!')
        return response
    
    def _extract_invoice_items(self):
        """Extract invoice items from POST data"""
        items = []
        post_data = self.request.POST
        
        # Find all item indices
        item_indices = set()
        for key in post_data.keys():
            if key.startswith('items[') and '][description]' in key:
                index = key.split('[')[1].split(']')[0]
                item_indices.add(index)
        
        # Extract data for each item
        for index in item_indices:
            description = post_data.get(f'items[{index}][description]', '')
            quantity = float(post_data.get(f'items[{index}][quantity]', 0))
            rate = float(post_data.get(f'items[{index}][rate]', 0))
            
            if description and quantity > 0:
                items.append({
                    'description': description,
                    'quantity': quantity,
                    'rate': rate,
                    'amount': quantity * rate
                })
        
        return items

class InvoiceDetailView(LoginRequiredMixin, TemplateView):
    """View invoice details"""
    template_name = 'billing/invoice_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice_id = kwargs.get('pk')
        invoice = get_object_or_404(AdvancedInvoice.objects.select_related('client', 'case', 'currency'), id=invoice_id)
        
        context.update({
            'invoice': invoice,
            'payments': invoice.payments.all(),
            'page_title': f'Invoice {invoice.invoice_number}'
        })
        return context

@login_required
@csrf_exempt
def record_payment(request, invoice_id):
    """Record payment for an invoice"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        invoice = get_object_or_404(AdvancedInvoice, id=invoice_id)
        
        amount = float(request.POST.get('amount', 0))
        payment_method = request.POST.get('payment_method')
        payment_date = request.POST.get('payment_date')
        notes = request.POST.get('notes', '')
        
        if amount <= 0:
            return JsonResponse({'success': False, 'error': 'Invalid amount'})
        
        # Create payment record
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            payment_date=payment_date,
            notes=notes,
            processed_by=request.user,
            currency=invoice.currency,
            status='completed'
        )
        
        # Update invoice status if fully paid
        total_payments = sum(p.amount for p in invoice.payments.all())
        if total_payments >= invoice.total_amount:
            invoice.status = 'paid'
            invoice.save()
        
        return JsonResponse({'success': True, 'message': 'Payment recorded successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def send_invoice(request, invoice_id):
    """Send invoice to client via email"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        invoice = get_object_or_404(AdvancedInvoice, id=invoice_id)
        
        # Update status to sent
        invoice.status = 'sent'
        invoice.save()
        
        # TODO: Implement actual email sending
        # send_invoice_email(invoice)
        
        return JsonResponse({'success': True, 'message': 'Invoice sent successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def download_invoice_pdf(request, invoice_id):
    """Download invoice as PDF"""
    try:
        invoice = get_object_or_404(AdvancedInvoice, id=invoice_id)
        
        # TODO: Implement PDF generation
        # For now, return a placeholder response
        response = HttpResponse('PDF generation not implemented yet', content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

@login_required
def get_time_entries(request, case_id):
    """Get time entries for a specific case (AJAX endpoint)"""
    try:
        case = get_object_or_404(Case, id=case_id)
        
        # Mock time entries data - replace with actual time tracking model
        time_entries = [
            {
                'id': 1,
                'date': '2024-01-15',
                'description': 'Client consultation',
                'hours': 2.0,
                'rate': 75.00
            },
            {
                'id': 2,
                'date': '2024-01-16',
                'description': 'Document review',
                'hours': 1.5,
                'rate': 60.00
            }
        ]
        
        return JsonResponse({'time_entries': time_entries})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# EXPENSE MANAGEMENT VIEWS

class ExpensesListView(LoginRequiredMixin, ListView):
    """List all expenses with filtering and pagination"""
    model = Expense
    template_name = 'billing/expenses_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Expense.objects.select_related('case', 'currency', 'user', 'category')
        
        category_filter = self.request.GET.get('category')
        if category_filter:
            queryset = queryset.filter(category__name=category_filter)
            
        billable_filter = self.request.GET.get('billable')
        if billable_filter:
            queryset = queryset.filter(is_billable=(billable_filter.lower() == 'true'))
            
        reimbursed_filter = self.request.GET.get('reimbursed')
        if reimbursed_filter:
            queryset = queryset.filter(is_billed=(reimbursed_filter.lower() == 'true'))
        
        return queryset.order_by('-expense_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate stats for the cards
        expenses = Expense.objects.all()
        current_month = timezone.now().replace(day=1)
        
        context.update({
            'pending_count': expenses.filter(is_billed=False).count(),
            'total_this_month': expenses.filter(
                expense_date__gte=current_month.date()
            ).aggregate(models.Sum('amount'))['amount__sum'] or 0,
            'total_reimbursed': expenses.filter(
                is_billed=True
            ).aggregate(models.Sum('amount'))['amount__sum'] or 0,
            'expense_categories': ExpenseCategory.objects.filter(is_active=True),
            'page_title': 'Expenses Management'
        })
        return context

class CreateExpenseView(LoginRequiredMixin, CreateView):
    """Create new expense"""
    model = Expense
    template_name = 'billing/create_expense.html'
    fields = ['description', 'expense_date', 'amount', 'currency', 'category', 'case', 'receipt', 'is_billable']
    success_url = reverse_lazy('expenses_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'cases': Case.objects.select_related('client'),
            'currencies': Currency.objects.all(),
            'categories': ExpenseCategory.objects.filter(is_active=True).order_by('name'),
            'today': date.today().isoformat(),
            'page_title': 'Add Expense'
        })
        return context
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        messages.success(self.request, 'Expense submitted successfully!')
        return super().form_valid(form)

class ExpenseDetailView(LoginRequiredMixin, TemplateView):
    """View expense details"""
    template_name = 'billing/expense_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expense_id = kwargs.get('pk')
        expense = get_object_or_404(Expense.objects.select_related('case', 'currency', 'user'), id=expense_id)
        
        context.update({
            'expense': expense,
            'page_title': f'Expense - {expense.description[:30]}'
        })
        return context

@login_required
def mark_expense_reimbursed(request, expense_id):
    """Mark expense as reimbursed"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        expense = get_object_or_404(Expense, id=expense_id)
        
        # Check permissions
        if request.user.role not in ['admin', 'lawyer']:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        expense.is_billed = True
        expense.save()
        
        return JsonResponse({'success': True, 'message': 'Expense marked as reimbursed'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# PAYMENTS TRACKING VIEWS

class PaymentsListView(LoginRequiredMixin, ListView):
    """List all payments with filtering and pagination"""
    model = Payment
    template_name = 'billing/payments_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Payment.objects.select_related('invoice', 'invoice__client', 'currency', 'processed_by')
        
        method_filter = self.request.GET.get('method')
        if method_filter:
            queryset = queryset.filter(payment_method=method_filter)
            
        date_filter = self.request.GET.get('date')
        if date_filter == 'today':
            queryset = queryset.filter(payment_date=date.today())
        elif date_filter == 'this_week':
            start_week = date.today() - timedelta(days=date.today().weekday())
            queryset = queryset.filter(payment_date__gte=start_week)
        elif date_filter == 'this_month':
            current_month = timezone.now().replace(day=1)
            queryset = queryset.filter(payment_date__gte=current_month)
        
        return queryset.order_by('-payment_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate stats for the cards
        payments = Payment.objects.all()
        current_month = timezone.now().replace(day=1)
        
        total_received = payments.aggregate(models.Sum('amount'))['amount__sum'] or 0
        total_this_month = payments.filter(
            payment_date__gte=current_month
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        count = payments.count()
        average_payment = total_received / count if count > 0 else 0
        
        context.update({
            'total_received': total_received,
            'total_this_month': total_this_month,
            'average_payment': average_payment,
            'page_title': 'Payments Management'
        })
        return context

@login_required
def payment_details(request, payment_id):
    """Get payment details (AJAX endpoint)"""
    try:
        payment = get_object_or_404(Payment.objects.select_related('invoice', 'invoice__client', 'currency'), id=payment_id)
        
        html_content = f"""
        <div class="row">
            <div class="col-md-6">
                <h6 class="text-muted">Payment Information</h6>
                <p><strong>Amount:</strong> {payment.currency.symbol if payment.currency else '€'}{payment.amount}</p>
                <p><strong>Date:</strong> {payment.payment_date.strftime('%B %d, %Y')}</p>
                <p><strong>Method:</strong> {payment.get_payment_method_display()}</p>
                {'<p><strong>Transaction ID:</strong> ' + payment.external_transaction_id + '</p>' if payment.external_transaction_id else ''}
                <p><strong>Recorded by:</strong> {payment.processed_by.get_full_name() if payment.processed_by else 'System'}</p>
            </div>
            <div class="col-md-6">
                <h6 class="text-muted">Invoice Information</h6>
                {'<p><strong>Invoice:</strong> <a href="/billing/invoices/' + str(payment.invoice.id) + '/">' + payment.invoice.invoice_number + '</a></p>' if payment.invoice else '<p>Manual Payment</p>'}
                {'<p><strong>Client:</strong> <a href="/clients/' + str(payment.invoice.client.id) + '/">' + (payment.invoice.client.company_name or payment.invoice.client.user.get_full_name()) + '</a></p>' if payment.invoice and payment.invoice.client else ''}
            </div>
        </div>
        {'<hr><h6 class="text-muted">Notes</h6><p>' + payment.notes + '</p>' if payment.notes else ''}
        """
        
        return JsonResponse({'success': True, 'html': html_content})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def payment_receipt(request, payment_id):
    """Generate payment receipt"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        # TODO: Implement actual receipt generation
        # For now, return a placeholder response
        response = HttpResponse(f'Payment Receipt for {payment.currency.symbol if payment.currency else "€"}{payment.amount}', 
                              content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="receipt_{payment_id}.pdf"'
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

@login_required
def export_payments(request):
    """Export payments to CSV"""
    import csv
    from django.http import HttpResponse
    
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Invoice', 'Client', 'Amount', 'Currency', 'Method', 'Reference', 'Notes'])
        
        payments = Payment.objects.select_related('invoice', 'invoice__client', 'currency')
        for payment in payments:
            writer.writerow([
                payment.payment_date,
                payment.invoice.invoice_number if payment.invoice else 'Manual',
                payment.invoice.client.company_name or payment.invoice.client.user.get_full_name() if payment.invoice and payment.invoice.client else '',
                payment.amount,
                payment.currency.code if payment.currency else 'EUR',
                payment.get_payment_method_display(),
                payment.external_transaction_id or '',
                payment.notes or ''
            ])
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

class RecordManualPaymentView(LoginRequiredMixin, CreateView):
    """Record a manual payment not tied to an invoice"""
    model = Payment
    template_name = 'billing/record_payment.html'
    fields = ['amount', 'currency', 'payment_method', 'payment_date', 'external_transaction_id', 'notes']
    success_url = reverse_lazy('payments_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'currencies': Currency.objects.all(),
            'today': date.today().isoformat(),
            'page_title': 'Record Payment'
        })
        return context
    
    def form_valid(self, form):
        form.instance.processed_by = self.request.user
        form.instance.status = 'completed'
        messages.success(self.request, 'Payment recorded successfully!')
        return super().form_valid(form)

# EXPENSE CATEGORIES MANAGEMENT

class ExpenseCategoriesListView(LoginRequiredMixin, ListView):
    """List all expense categories"""
    model = ExpenseCategory
    template_name = 'billing/expense_categories.html'
    context_object_name = 'categories'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Expense Categories',
            'total_categories': ExpenseCategory.objects.count(),
            'active_categories': ExpenseCategory.objects.filter(is_active=True).count(),
        })
        return context

class CreateExpenseCategoryView(LoginRequiredMixin, CreateView):
    """Create new expense category"""
    model = ExpenseCategory
    template_name = 'billing/create_expense_category.html'
    fields = ['name', 'description', 'is_billable', 'default_markup_percentage', 'is_active']
    success_url = reverse_lazy('expense_categories')
    
    def form_valid(self, form):
        messages.success(self.request, 'Expense category created successfully!')
        return super().form_valid(form)

class UpdateExpenseCategoryView(LoginRequiredMixin, UpdateView):
    """Update expense category"""
    model = ExpenseCategory
    template_name = 'billing/create_expense_category.html'
    fields = ['name', 'description', 'is_billable', 'default_markup_percentage', 'is_active']
    success_url = reverse_lazy('expense_categories')
    
    def form_valid(self, form):
        messages.success(self.request, 'Expense category updated successfully!')
        return super().form_valid(form)

@login_required
def delete_expense_category(request, category_id):
    """Delete expense category (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        category = get_object_or_404(ExpenseCategory, id=category_id)
        
        # Check if category is in use
        expenses_count = Expense.objects.filter(category=category).count()
        if expenses_count > 0:
            return JsonResponse({
                'success': False, 
                'error': f'Cannot delete category. It is being used by {expenses_count} expense(s).'
            })
        
        category_name = category.name
        category.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Category "{category_name}" deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# EXPENSE REPORTING AND ANALYTICS

@login_required 
def expense_export(request):
    """Export expenses to CSV"""
    import csv
    from django.http import HttpResponse
    
    try:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expenses_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Description', 'Category', 'Case', 'Client', 'Amount', 'Currency', 
            'Billable Amount', 'Markup %', 'Billable', 'Reimbursed', 'Submitted By'
        ])
        
        expenses = Expense.objects.select_related('case', 'category', 'currency', 'user').all()
        for expense in expenses:
            writer.writerow([
                expense.expense_date,
                expense.description,
                expense.category.name,
                expense.case.title if expense.case else '',
                expense.case.client.full_name if expense.case else '',
                expense.amount,
                expense.currency.code if expense.currency else 'EUR',
                expense.billable_amount or '',
                expense.markup_percentage,
                'Yes' if expense.is_billable else 'No',
                'Yes' if expense.is_billed else 'No',
                expense.user.get_full_name() or expense.user.username
            ])
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

@login_required
def expense_analytics(request):
    """Expense analytics and reporting"""
    try:
        # Get date filters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        expenses = Expense.objects.all()
        
        if start_date:
            expenses = expenses.filter(expense_date__gte=start_date)
        if end_date:
            expenses = expenses.filter(expense_date__lte=end_date)
        
        # Calculate analytics
        total_expenses = expenses.aggregate(models.Sum('amount'))['amount__sum'] or 0
        total_billable = expenses.filter(is_billable=True).aggregate(models.Sum('billable_amount'))['billable_amount__sum'] or 0
        total_reimbursed = expenses.filter(is_billed=True).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        # Category breakdown
        category_stats = expenses.values('category__name').annotate(
            total_amount=models.Sum('amount'),
            count=models.Count('id')
        ).order_by('-total_amount')
        
        # Monthly trend
        monthly_stats = expenses.extra(
            select={'month': 'DATE_FORMAT(expense_date, "%%Y-%%m")'}
        ).values('month').annotate(
            total_amount=models.Sum('amount'),
            count=models.Count('id')
        ).order_by('month')
        
        analytics_data = {
            'total_expenses': total_expenses,
            'total_billable': total_billable,
            'total_reimbursed': total_reimbursed,
            'pending_reimbursement': total_expenses - total_reimbursed,
            'category_breakdown': list(category_stats),
            'monthly_trend': list(monthly_stats),
            'total_count': expenses.count()
        }
        
        return JsonResponse({
            'success': True,
            'data': analytics_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def duplicate_expense(request, expense_id):
    """Duplicate an existing expense"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        original_expense = get_object_or_404(Expense, id=expense_id)
        
        # Create duplicate
        new_expense = Expense.objects.create(
            case=original_expense.case,
            category=original_expense.category,
            user=request.user,
            description=f"Copy of {original_expense.description}",
            amount=original_expense.amount,
            currency=original_expense.currency,
            markup_percentage=original_expense.markup_percentage,
            is_billable=original_expense.is_billable,
            expense_date=date.today(),
            # Don't copy receipt or billable status
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Expense duplicated successfully!',
            'expense_id': new_expense.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})