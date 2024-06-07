from django.urls import path
from user import views

urlpatterns = [
    path('login', views.send_registration_email, name="send-registration-email-url"),
    path('userManage/personal/<str:username>',views.get_user_info,name='get-user-info-url'),

    #path('user/updateUserInfo',views.update_user_email, name='update-user-info-url'),
    path('userManage/unreleased/<str:username>',views.get_drafted_qs,name='get-drafted-qs-url'),
    path('userManage/released/<str:username>',views.get_released_qs,name='get-released-qs-url'),
    path('userManage/filled/<str:username>',views.get_filled_qs,name='get-filled-qs-url'),
    path('userManage/square',views.get_all_released_qs,name='get-all-released-qs-url'),
    path('userManage/unreleased',views.delete_unreleased_qs,name='delete-unreleased-qs-url'),
    #path('userManage/released',views.delete_released_qs,name='delete-released-qs-url'),
]