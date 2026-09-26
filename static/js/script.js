document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  document.getElementById('menuToggle')?.addEventListener('click', () => sidebar?.classList.toggle('open'));
  document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', e => {
    if (!window.confirm(form.dataset.confirm || 'Are you sure?')) e.preventDefault();
  }));
  document.querySelectorAll('.alert').forEach(alert => setTimeout(() => bootstrap.Alert.getOrCreateInstance(alert).close(), 5500));
  document.querySelectorAll('.clear-search').forEach(button => button.addEventListener('click', () => {
    const input = button.closest('.search-field')?.querySelector('input');
    if (input) { input.value = ''; input.focus(); }
  }));
  const department = document.getElementById('departmentSelect');
  const doctor = document.getElementById('doctorSelect');
  const day = document.getElementById('appointmentDate');
  const time = document.getElementById('timeSelect');
  const feeHint = document.getElementById('feeHint');
  const legend = document.getElementById('slotLegend');
  async function loadDoctors() {
    if (!department || !doctor) return;
    doctor.innerHTML = '<option value="">Loading doctors…</option>'; doctor.disabled = true;
    if (!department.value) { doctor.innerHTML = '<option value="">Choose department first</option>'; return; }
    try {
      const data = await fetch(`/api/doctors/${department.value}`).then(r => r.json());
      doctor.innerHTML = '<option value="">Select doctor</option>' + data.doctors.map(d => `<option value="${d.id}" data-fee="${d.fee}">${escapeHtml(d.name)} · ${escapeHtml(d.specialization || '')}</option>`).join('');
      doctor.disabled = !data.doctors.length;
      if (!data.doctors.length) doctor.innerHTML = '<option value="">No active doctors</option>';
    } catch { doctor.innerHTML = '<option value="">Unable to load doctors</option>'; }
    loadSlots();
  }
  async function loadSlots() {
    if (!doctor || !day || !time) return;
    const selected = doctor.selectedOptions[0];
    feeHint.textContent = selected?.dataset.fee ? `Consultation fee: ₹${Number(selected.dataset.fee).toFixed(0)}` : '';
    time.disabled = true; time.innerHTML = '<option value="">Select doctor and date</option>'; legend?.classList.add('d-none');
    if (!doctor.value || !day.value) return;
    time.innerHTML = '<option value="">Loading available slots…</option>';
    try {
      const data = await fetch(`/api/available-slots/${doctor.value}/${day.value}`).then(r => r.json());
      const slots = data.slots || [];
      if (!slots.length) { time.innerHTML = '<option value="">No schedule on this date</option>'; return; }
      time.innerHTML = '<option value="">Select a time</option>' + slots.map(s => `<option value="${s.time}" ${s.available ? '' : 'disabled'}>${s.time} · ${s.available ? 'Available' : 'Booked'}</option>`).join('');
      time.disabled = false; legend?.classList.remove('d-none');
    } catch { time.innerHTML = '<option value="">Unable to load slots</option>'; }
  }
  department?.addEventListener('change', loadDoctors);
  doctor?.addEventListener('change', loadSlots);
  day?.addEventListener('change', loadSlots);
  const paymentAppointment = document.getElementById('paymentAppointment');
  paymentAppointment?.addEventListener('change', () => {
    const fee = paymentAppointment.selectedOptions[0]?.dataset.fee;
    const target = document.getElementById('consultationFee');
    if (target) target.value = fee ? Number(fee).toFixed(2) : '';
  });
  const period = document.getElementById('reportPeriod');
  period?.addEventListener('change', () => document.querySelectorAll('.custom-report-date').forEach(el => el.required = period.value === 'custom'));
});
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
