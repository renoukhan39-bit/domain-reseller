from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("signup/", views.signup, name="signup"),
    path("accounts/verification/resend/", views.resend_verification, name="resend_verification"),
    path("accounts/verification/sent/", views.resend_verification_done, name="resend_verification_done"),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path("contact/", views.contact, name="contact"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("buy/<str:domain>/", views.buy, name="buy"),
    path("renew/<int:domain_id>/", views.renew, name="renew"),
    path("orders/<uuid:order_id>/", views.order_detail, name="order_detail"),
    path("domains/<int:domain_id>/nameservers/", views.nameservers, name="nameservers"),
    path("webhooks/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),
]
