"""
Billing Service për Auto-generation të faturave dhe logjikën e faturimit
"""

from django.utils import timezone
from django.db import transaction
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from decimal import Decimal
from datetime import timedelta, date
import uuid
from typing import List, Dict, Optional

from ..models import Case, Client, TimeEntry
from ..models_billing import (
    AdvancedInvoice, InvoiceTimeEntry, InvoiceExpenseItem, 
    Expense, BillingRate, Currency, RecurringInvoice, Payment
)

class BillingService:
    """
    Shërbimi kryesor për faturimin
    """
    
    def __init__(self):
        self.default_currency = Currency.objects.filter(is_base_currency=True).first()
        if not self.default_currency:
            # Nëse nuk ka valutë bazë, krijon një default
            self.default_currency = Currency.objects.create(
                code='EUR',
                name='Euro',
                symbol='€',
                is_base_currency=True
            )
    
    @transaction.atomic
    def generate_invoice_for_case(
        self, 
        case: Case, 
        period_start: date = None, 
        period_end: date = None,
        auto_send: bool = False,
        user = None
    ) -> AdvancedInvoice:
        """
        Gjeneron faturë automatike për një rast për periudhën e specifikuar
        """
        if not period_end:
            period_end = timezone.now().date()
        if not period_start:
            period_start = period_end - timedelta(days=30)  # Default 30 ditë
        
        # Merr time entries që nuk janë faturuar ende
        unbilled_time_entries = TimeEntry.objects.filter(
            case=case,
            created_at__date__range=[period_start, period_end]
        ).exclude(
            invoicetimeentry__isnull=False
        )
        
        # Merr shpenzimet që nuk janë faturuar ende
        unbilled_expenses = Expense.objects.filter(
            case=case,
            expense_date__range=[period_start, period_end],
            is_billable=True,
            is_billed=False
        )
        
        if not unbilled_time_entries.exists() and not unbilled_expenses.exists():
            raise ValueError("Nuk ka hyrje të pa-faturuara për këtë periudhë")
        
        # Krijon faturën
        invoice = AdvancedInvoice.objects.create(
            case=case,
            client=case.client,
            currency=self.default_currency,
            due_date=period_end + timedelta(days=30),  # 30 ditë për pagesë
            is_auto_generated=True,
            auto_send=auto_send,
            created_by=user or case.assigned_lawyer,
            notes=f"Faturë automatike për periudhën {period_start} - {period_end}"
        )
        
        # Shton time entries
        for time_entry in unbilled_time_entries:
            billing_rate = self._get_billing_rate_for_user(time_entry.user, case)
            if billing_rate:
                InvoiceTimeEntry.objects.create(
                    invoice=invoice,
                    time_entry=time_entry,
                    billing_rate=billing_rate
                )
        
        # Shton shpenzimet
        for expense in unbilled_expenses:
            InvoiceExpenseItem.objects.create(
                invoice=invoice,
                expense=expense
            )
            expense.is_billed = True
            expense.save()
        
        # Llogarit totalet
        invoice.calculate_totals()
        invoice.save()
        
        # Dërgon faturën automatikisht nëse është kërkuar
        if auto_send:
            self.send_invoice_email(invoice)
        
        return invoice
    
    def _get_billing_rate_for_user(self, user, case) -> Optional[BillingRate]:
        """
        Merr tarifën e faturimit për përdoruesin dhe rastin
        """
        # Përparon të gjejë tarifë specifike për përdoruesin
        rate = BillingRate.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if not rate:
            # Kërkon tarifë për kategorinë e rastit
            rate = BillingRate.objects.filter(
                case_category=case.category,
                user__isnull=True,
                is_active=True
            ).first()
        
        if not rate:
            # Tarifa default
            rate = BillingRate.objects.filter(
                rate_type='hourly',
                user__isnull=True,
                case_category__isnull=True,
                is_active=True
            ).first()
        
        return rate
    
    def generate_recurring_invoices(self):
        """
        Gjeneron faturat periodike që janë gati për t'u krijuar
        """
        today = timezone.now().date()
        
        recurring_invoices = RecurringInvoice.objects.filter(
            is_active=True,
            next_invoice_date__lte=today
        )
        
        generated_invoices = []
        
        for recurring in recurring_invoices:
            try:
                # Llogarit periudhën e faturimit
                period_end = recurring.next_invoice_date
                
                if recurring.frequency == 'monthly':
                    period_start = period_end - timedelta(days=30)
                    next_date = period_end + timedelta(days=30)
                elif recurring.frequency == 'weekly':
                    period_start = period_end - timedelta(days=7)
                    next_date = period_end + timedelta(days=7)
                elif recurring.frequency == 'quarterly':
                    period_start = period_end - timedelta(days=90)
                    next_date = period_end + timedelta(days=90)
                elif recurring.frequency == 'yearly':
                    period_start = period_end - timedelta(days=365)
                    next_date = period_end + timedelta(days=365)
                
                # Gjeneron faturën
                invoice = self.generate_invoice_for_case(
                    case=recurring.case,
                    period_start=period_start,
                    period_end=period_end,
                    auto_send=True
                )
                
                # Përditëson datën e ardhshme
                recurring.next_invoice_date = next_date
                recurring.save()
                
                generated_invoices.append(invoice)
                
            except Exception as e:
                # Log error dhe vazhdon me të tjerat
                print(f"Error generating recurring invoice {recurring.id}: {e}")
                continue
        
        return generated_invoices
    
    def send_invoice_email(self, invoice: AdvancedInvoice) -> bool:
        """
        Dërgon faturën via email
        """
        try:
            # Gjeneron PDF-në e faturës
            pdf_content = self.generate_invoice_pdf(invoice)
            
            # Krijon email-in
            subject = f"Fatura {invoice.invoice_number} - {invoice.case.title}"
            
            context = {
                'invoice': invoice,
                'client': invoice.client,
                'case': invoice.case,
            }
            
            html_content = render_to_string('billing/invoice_email.html', context)
            
            email = EmailMessage(
                subject=subject,
                body=html_content,
                from_email='noreply@legalsystem.com',
                to=[invoice.client.email],
                cc=[invoice.case.assigned_lawyer.email] if invoice.case.assigned_lawyer else []
            )
            
            email.content_subtype = 'html'
            
            # Bashkëngjit PDF-në
            email.attach(
                f'Invoice_{invoice.invoice_number}.pdf',
                pdf_content,
                'application/pdf'
            )
            
            email.send()
            
            # Përditëson statusin e faturës
            invoice.status = 'sent'
            invoice.save()
            
            return True
            
        except Exception as e:
            print(f"Error sending invoice email: {e}")
            return False
    
    def generate_invoice_pdf(self, invoice: AdvancedInvoice) -> bytes:
        """
        Gjeneron PDF për faturën
        """
        # Për tani kthejmë një placeholder
        # Në implementim real, do të përdorim biblioteka si reportlab ose weasyprint
        return b"PDF content placeholder"
    
    def process_payment(
        self, 
        invoice: AdvancedInvoice, 
        amount: Decimal, 
        payment_method: str,
        external_transaction_id: str = None,
        processed_by = None
    ) -> Payment:
        """
        Procesó një pagesë për faturën
        """
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            currency=invoice.currency,
            payment_method=payment_method,
            external_transaction_id=external_transaction_id,
            status='completed',
            processed_by=processed_by
        )
        
        # Kontrollón nëse fatura është paguar plotësisht
        total_payments = invoice.payments.filter(
            status='completed'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        if total_payments >= invoice.total_amount:
            invoice.status = 'paid'
            invoice.save()
        
        return payment
    
    def get_billing_summary(self, case: Case, year: int = None) -> Dict:
        """
        Merr përmbledhjen e faturimit për një rast
        """
        if not year:
            year = timezone.now().year
        
        invoices = AdvancedInvoice.objects.filter(
            case=case,
            issue_date__year=year
        )
        
        total_billed = invoices.aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0')
        
        total_paid = Payment.objects.filter(
            invoice__case=case,
            invoice__issue_date__year=year,
            status='completed'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        outstanding = total_billed - total_paid
        
        return {
            'total_billed': total_billed,
            'total_paid': total_paid,
            'outstanding': outstanding,
            'invoice_count': invoices.count(),
            'paid_invoice_count': invoices.filter(status='paid').count(),
        }

class ExpenseTrackingService:
    """
    Shërbimi për tracking të shpenzimeve
    """
    
    def create_expense(
        self,
        case: Case,
        category_id: int,
        description: str,
        amount: Decimal,
        currency: Currency,
        user,
        expense_date: date = None,
        receipt_file = None,
        is_billable: bool = True
    ) -> Expense:
        """
        Krijon një shpenzim të ri
        """
        if not expense_date:
            expense_date = timezone.now().date()
        
        expense = Expense.objects.create(
            case=case,
            category_id=category_id,
            description=description,
            amount=amount,
            currency=currency,
            user=user,
            expense_date=expense_date,
            receipt=receipt_file,
            is_billable=is_billable
        )
        
        return expense
    
    def get_case_expenses_summary(self, case: Case, year: int = None) -> Dict:
        """
        Merr përmbledhjen e shpenzimeve për një rast
        """
        if not year:
            year = timezone.now().year
        
        expenses = Expense.objects.filter(
            case=case,
            expense_date__year=year
        )
        
        billable_expenses = expenses.filter(is_billable=True)
        billed_expenses = expenses.filter(is_billed=True)
        
        return {
            'total_expenses': expenses.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0'),
            'billable_expenses': billable_expenses.aggregate(
                total=models.Sum('billable_amount')
            )['total'] or Decimal('0'),
            'billed_expenses': billed_expenses.aggregate(
                total=models.Sum('billable_amount')
            )['total'] or Decimal('0'),
            'unbilled_billable': billable_expenses.filter(
                is_billed=False
            ).aggregate(
                total=models.Sum('billable_amount')
            )['total'] or Decimal('0'),
        }

# Import models për të shmangur circular imports
from django.db import models