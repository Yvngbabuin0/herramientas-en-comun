from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class SoloEncargadoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo el encargado (is_staff). Sin sesión redirige al login; un socio recibe 403."""

    def test_func(self):
        return self.request.user.is_staff
