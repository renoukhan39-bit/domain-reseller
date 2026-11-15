from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from shop import views
from shop.forms import SafePasswordResetForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(form_class=SafePasswordResetForm, template_name="shop/password_reset_form.html", email_template_name="shop/password_reset_email.html"), name="password_reset"),
    path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="shop/password_reset_done.html"), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="shop/password_reset_confirm.html"), name="password_reset_confirm"),
    path("accounts/reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name="shop/password_reset_complete.html"), name="password_reset_complete"),
    path("", include("shop.urls")),
]
