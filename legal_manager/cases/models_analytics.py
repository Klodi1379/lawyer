"""
Advanced Analytics & Reporting Models për Legal Case Manager
Përfshin: Financial reports, Performance metrics, Case outcome analysis, Time utilization
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from decimal import Decimal
import json
from datetime import date, timedelta
from .models import Case, Client, User, TimeEntry
from .models_billing import AdvancedInvoice, Payment, Expense, Currency

User = get_user_model()

class AnalyticsReport(models.Model):
    """
    Raporte analitike të gjeneruara automatikisht
    """
    REPORT_TYPE_CHOICES = [
        ('financial', 'Raporti Financiar'),
        ('performance', 'Performancë'),
        ('productivity', 'Produktiviteti'),
        ('client_satisfaction', 'Kënaqësia e Klientit'),
        ('case_outcome', 'Rezultatet e Rasteve'),
        ('time_utilization', 'Përdorimi i Kohës'),
        ('revenue_forecast', 'Parashikimi i të Ardhurave'),
    ]
    
    PERIOD_TYPE_CHOICES = [
        ('daily', 'Ditore'),
        ('weekly', 'Javore'),
        ('monthly', 'Mujore'),
        ('quarterly', 'Tremujore'),
        ('yearly', 'Vjetore'),
        ('custom', 'E Personalizuar'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="Emri i Raportit")
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES)
    
    # Periudha e raportit
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Filtrat dhe parametrat
    filters = models.JSONField(default=dict, blank=True, verbose_name="Filtrat")
    parameters = models.JSONField(default=dict, blank=True, verbose_name="Parametrat")
    
    # Data e raportit
    report_data = models.JSONField(verbose_name="Të Dhënat e Raportit")
    summary_data = models.JSONField(default=dict, verbose_name="Përmbledhja")
    
    # Metadata
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_scheduled = models.BooleanField(default=False, verbose_name="I Planifikuar")
    
    class Meta:
        verbose_name = "Raporti Analitik"
        verbose_name_plural = "Raportet Analitike"
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

class FinancialMetrics(models.Model):
    """
    Metritat financiare të llogarìtura automatikisht
    """
    # Periudha
    date = models.DateField(unique=True)
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    billable_hours_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    expense_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Invoice metrics
    total_invoiced = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_collected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Collection metrics
    collection_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Përqindje
    average_collection_time = models.PositiveIntegerField(default=0)  # Ditë
    
    # Case metrics
    active_cases_count = models.PositiveIntegerField(default=0)
    new_cases_count = models.PositiveIntegerField(default=0)
    closed_cases_count = models.PositiveIntegerField(default=0)
    
    # Billable hours
    total_billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Expenses
    total_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    billable_expenses = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Metrikat Financiare"
        verbose_name_plural = "Metrikat Financiare"
        ordering = ['-date']
    
    def __str__(self):
        return f"Financial Metrics - {self.date}"

class UserPerformanceMetrics(models.Model):
    """
    Metritat e performancës për përdoruesit
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance_metrics')
    date = models.DateField()
    
    # Time tracking
    total_hours_logged = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    non_billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    utilization_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Përqindje
    
    # Revenue generation
    revenue_generated = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Case management
    active_cases_count = models.PositiveIntegerField(default=0)
    cases_opened = models.PositiveIntegerField(default=0)
    cases_closed = models.PositiveIntegerField(default=0)
    
    # Client interaction
    client_meetings = models.PositiveIntegerField(default=0)
    documents_created = models.PositiveIntegerField(default=0)
    
    # Productivity metrics
    tasks_completed = models.PositiveIntegerField(default=0)
    deadlines_met = models.PositiveIntegerField(default=0)
    deadlines_missed = models.PositiveIntegerField(default=0)
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Metritat e Performancës së Përdoruesit"
        verbose_name_plural = "Metritat e Performancës së Përdoruesve"
        unique_together = ['user', 'date']
        ordering = ['-date', 'user']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.date}"

class CaseOutcomeMetrics(models.Model):
    """
    Metritat e rezultateve të rasteve
    """
    OUTCOME_CHOICES = [
        ('won', 'Fituar'),
        ('lost', 'Humbur'),
        ('settled', 'Marrëveshje'),
        ('dismissed', 'Hedhur poshtë'),
        ('ongoing', 'Në vijim'),
        ('withdrawn', 'Tërhequr'),
    ]
    
    case = models.OneToOneField(Case, on_delete=models.CASCADE, related_name='outcome_metrics')
    
    # Rezultati
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, null=True, blank=True)
    outcome_date = models.DateField(null=True, blank=True)
    
    # Financial outcomes
    amount_claimed = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    amount_awarded = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    settlement_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Time metrics
    total_duration_days = models.PositiveIntegerField(null=True, blank=True)
    time_to_resolution_days = models.PositiveIntegerField(null=True, blank=True)
    
    # Cost metrics
    total_legal_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    client_satisfaction_score = models.PositiveIntegerField(null=True, blank=True)  # 1-5
    
    # Success metrics
    success_rate_factor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Metritat e Rezultatit të Rastit"
        verbose_name_plural = "Metritat e Rezultateve të Rasteve"
    
    def calculate_success_rate_factor(self):
        """Llogarit faktorin e suksesit bazuar në rezultat dhe sasi"""
        if self.outcome == 'won':
            if self.amount_awarded and self.amount_claimed:
                return (self.amount_awarded / self.amount_claimed) * 100
            return 100
        elif self.outcome == 'settled':
            if self.settlement_amount and self.amount_claimed:
                return (self.settlement_amount / self.amount_claimed) * 100
            return 50
        elif self.outcome == 'lost':
            return 0
        return None
    
    def save(self, *args, **kwargs):
        if self.outcome and not self.success_rate_factor:
            self.success_rate_factor = self.calculate_success_rate_factor()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.case.title} - {self.get_outcome_display()}"

class ClientSatisfactionMetrics(models.Model):
    """
    Metritat e kënaqësisë së klientëve
    """
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='satisfaction_metrics')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, null=True, blank=True)
    
    # Vlerësimet (1-5)
    overall_satisfaction = models.PositiveIntegerField()
    communication_rating = models.PositiveIntegerField()
    quality_rating = models.PositiveIntegerField()
    timeliness_rating = models.PositiveIntegerField()
    value_rating = models.PositiveIntegerField()
    
    # Net Promoter Score
    nps_score = models.IntegerField(null=True, blank=True)  # 0-10
    would_recommend = models.BooleanField(null=True)
    
    # Feedback kategoriak
    positive_aspects = models.JSONField(default=list, blank=True)
    improvement_areas = models.JSONField(default=list, blank=True)
    
    survey_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Metritat e Kënaqësisë së Klientit"
        verbose_name_plural = "Metritat e Kënaqësisë së Klientëve"
        ordering = ['-survey_date']
    
    def calculate_average_rating(self):
        """Llogarit mesataren e vlerësimeve"""
        ratings = [
            self.overall_satisfaction,
            self.communication_rating,
            self.quality_rating,
            self.timeliness_rating,
            self.value_rating
        ]
        return sum(ratings) / len(ratings)
    
    def __str__(self):
        return f"{self.client.name} - {self.overall_satisfaction}/5"

class TimeUtilizationReport(models.Model):
    """
    Raportet e përdorimit të kohës
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_reports')
    
    # Periudha
    report_date = models.DateField()
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Orët e punës
    total_work_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    non_billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Breakdown sipas aktiviteteve
    case_work_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    admin_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    meeting_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    research_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Breakdown sipas klientëve/rasteve
    client_breakdown = models.JSONField(default=dict, blank=True)
    case_breakdown = models.JSONField(default=dict, blank=True)
    
    # Metritat e efikasitetit
    utilization_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    efficiency_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Raporti i Përdorimit të Kohës"
        verbose_name_plural = "Raportet e Përdorimit të Kohës"
        unique_together = ['user', 'report_date']
        ordering = ['-report_date']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.report_date}"

class RevenueForecasting(models.Model):
    """
    Parashikimi i të ardhurave
    """
    FORECAST_TYPE_CHOICES = [
        ('monthly', 'Mujore'),
        ('quarterly', 'Tremujore'),
        ('yearly', 'Vjetore'),
    ]
    
    forecast_type = models.CharField(max_length=20, choices=FORECAST_TYPE_CHOICES)
    forecast_period = models.DateField(verbose_name="Periudha e Parashikuar")
    
    # Parashikimet
    projected_revenue = models.DecimalField(max_digits=15, decimal_places=2)
    projected_billable_hours = models.DecimalField(max_digits=10, decimal_places=2)
    projected_new_cases = models.PositiveIntegerField()
    
    # Faktori i besueshmërisë
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2)  # Përqindje
    
    # Metodologjia e përdorur
    methodology = models.CharField(max_length=100, verbose_name="Metodologjia")
    assumptions = models.JSONField(default=dict, verbose_name="Supozimet")
    
    # Historical data e përdorur
    historical_data_start = models.DateField()
    historical_data_end = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Parashikimi i të Ardhurave"
        verbose_name_plural = "Parashikimet e të Ardhurave"
        unique_together = ['forecast_type', 'forecast_period']
        ordering = ['-forecast_period']
    
    def __str__(self):
        return f"Revenue Forecast - {self.forecast_period} ({self.get_forecast_type_display()})"

class KPI(models.Model):
    """
    Key Performance Indicators të personalizuara
    """
    KPI_TYPE_CHOICES = [
        ('financial', 'Financiare'),
        ('operational', 'Operacionale'),
        ('client', 'Klienti'),
        ('efficiency', 'Efikasiteti'),
        ('growth', 'Rritja'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Emri")
    description = models.TextField(verbose_name="Përshkrimi")
    kpi_type = models.CharField(max_length=20, choices=KPI_TYPE_CHOICES)
    
    # Metrikat
    current_value = models.DecimalField(max_digits=15, decimal_places=2)
    target_value = models.DecimalField(max_digits=15, decimal_places=2)
    previous_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Unit dhe format
    unit = models.CharField(max_length=20, default='number')  # number, percentage, currency, hours
    format_string = models.CharField(max_length=50, default='{value}')
    
    # Trends
    trend_direction = models.CharField(max_length=10, default='up')  # up, down, stable
    percentage_change = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Metadata
    calculation_method = models.TextField(verbose_name="Metoda e Llogaritjes")
    update_frequency = models.CharField(max_length=20, default='daily')
    
    last_updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPI-të"
        ordering = ['kpi_type', 'name']
    
    def calculate_performance_percentage(self):
        """Llogarit përqindjen e performances kundrejt target-it"""
        if self.target_value == 0:
            return 0
        return (self.current_value / self.target_value) * 100
    
    def __str__(self):
        return f"{self.name} ({self.get_kpi_type_display()})"