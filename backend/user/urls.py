from django.urls import path
from user import views

urlpatterns = [
    path('login', views.send_registration_email, name="send-registration-email-url"),
    #path('user/updateUserInfo',views.update_user_email, name='update-user-info-url'),
    #path('userManage/unreleased',views.get_qs_drafted,name='get-qs-drafted-url'),
    path('userManage/unreleased/<str:username>',views.get_drafted_qs,name='get-drafted-qs-url'),
    path('userManage/released/<str:username>',views.get_released_qs,name='get-released-qs-url'),
    path('userManage/filled/<str:username>',views.get_filled_qs,name='get-filled-qs-url'),
    path('userManage/square',views.get_all_released_qs,name='get-all-released-qs-url')
]