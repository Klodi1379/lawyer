
class EventCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CaseEvent
    form_class = EventForm
    template_name = 'events/event_form.html'

    def test_func(self):
        return self.request.user.role in ['admin', 'lawyer', 'paralegal']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        case_id = self.kwargs.get('case_pk')
        if case_id:
            kwargs['case'] = get_object_or_404(Case, pk=case_id)
        return kwargs

    def form_valid(self, form):
        case_id = self.kwargs.get('case_pk')
        if case_id:
            form.instance.case = get_object_or_404(Case, pk=case_id)
        form.instance.created_by = self.request.user
        
        response = super().form_valid(form)
        
        AuditLog.objects.create(
            user=self.request.user,
            action='event_create',
            target_type='CaseEvent',
            target_id=str(self.object.id),
            metadata={'event_title': self.object.title, 'case_id': self.object.case.id}
        )
        
        return response

    def get_success_url(self):
        if self.kwargs.get('case_pk'):
            return reverse_lazy('case_detail', kwargs={'pk': self.kwargs['case_pk']})
        else:
            return reverse_lazy('event_calendar')
