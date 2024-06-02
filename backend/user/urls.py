from django.urls import path
from user import views

urlpatterns = [
    path('login', views.send_registration_email, name="send-registration-email-url"),
    #path('user/updateUserInfo',views.update_user_email, name='update-user-info-url'),
    #path('userManage/unreleased',views.get_qs_drafted,name='get-qs-drafted-url'),
    #path('userManage/released',views.get_drafted_qs,name='get-drafted-qs-url'),
]