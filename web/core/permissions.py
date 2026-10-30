from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Refuse l'accès si le rôle de l'utilisateur n'est pas dans allowed_roles."""
    allowed_roles = ()

    def test_func(self):
        return self.request.user.role in self.allowed_roles