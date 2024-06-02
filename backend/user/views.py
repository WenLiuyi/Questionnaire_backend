from django.shortcuts import render
from django.http import JsonResponse

# Create your views here.
from .models import User,Survey
from .models import BaseQuestion,BlankQuestion,ChoiceQuestion,ChoiceOption,RatingQuestion
from .models import Answer,BlankAnswer,ChoiceAnswer,RatingAnswer
from .models import Submission,SurveyStatistic,Template,RewardOffering,UserRewardRecord   

import json
from django.core.mail import BadHeaderError, send_mail
from django.http import HttpResponse, HttpResponseRedirect

from django.core.mail import EmailMessage

from itsdangerous import URLSafeTimedSerializer as utsr
import base64
from django.conf import settings as django_settings
from django.utils import timezone

serveAddress="http:127.0.0.1:8080"

def get_user_info(request):
    if(request.method=='GET'):
        body=json.loads(request.body)
        username=body['username']
        
        user=User.objects.filter(username=username)
        data={
            'userid':user.UserID,
            'nickname':user.username,
            'email':user.email,

        }
        return JsonResponse(data)
    
def update_user_email(request):
    if(request.method=='POST'):
        body=json.loads(request.body)
        username=body['username']
        email=body['email']

        user=User.objects.filter(username=username)
        user.email=email

        user.save()

        return HttpResponse(status_code=200,content='Email updated successfully.')
    
def update_user_password(request):
    if(request.method=='POST'):
        data=json.loads(request.body)
        username=request.POST.get("username")
        password=request.POST.get("password")

        user=User.objects.filter(username=username)
        user.password=password

        user.save()

        return HttpResponse(status_code=200,content='Password updated successfully.')


class Token:
    def __init__(self, security_key):
        self.security_key = security_key
        # salt是秘钥的编码
        self.salt = base64.encodebytes(security_key.encode('utf-8'))
        #security_key是settings.py中SECURITY_KEY
        #salt是经过base64加密的SECURITY_KEY

    # 生成token,token中可以保存一段信息，这里我们选择保存username
    def generate_validate_token(self, username):
        serializer = utsr(self.security_key)            #生成令牌serializer
        return serializer.dumps(username, self.salt)    #username在令牌中被编码
        #将带有token的验证链接发送至注册邮箱

    # 验证token
    def confirm_validate_token(self, token, expiration=3600):
        serializer = utsr(self.security_key)
        return serializer.loads(token, salt=self.salt, max_age=expiration)

    # 删除token
    def remove_validate_token(self, token):
        serializer = utsr(self.security_key)
        print(serializer.loads(token, salt=self.salt))
        return serializer.loads(token, salt=self.salt)

token_confirm = Token(django_settings.SECRET_KEY)
def get_token(request):

    url = serveAddress+'user/' + token_confirm.generate_validate_token(username='username')
    '''此处将这个url发送到客户邮箱，我们这里就不进行邮件发送的操作了'''
    return HttpResponse(status_code=200,content='Send registration email successfully.')

def send_registration_email(request):
    if(request.method=='POST'):
        body=json.loads(request.body)
        user=User()
        username=body['username']
        password=body['password']
        email=body['email']

        user=User.objects.filter(username=username)
        if user.exists():
            return HttpResponse(status=200,content=False)

        #创建新用户(尚未邮箱验证,非有效用户)
        user=User.objects.create(username=username,email=email,
                                     password=password,CreateDate=timezone.now(),isActive=False)
        user.save()

        #生成令牌
        token = token_confirm.generate_validate_token(username)
        #active_key = base64.encodestring(userName)
        url="/login"

        #发送邮件
        subject="'纸翼传问'新用户注册"
        message=("你好,"+username+"! 欢迎注册“纸翼传问”!\n"
                     +"请点击以下链接，以激活新账户:\n"
                     +serveAddress+url)

        email=EmailMessage(subject=subject,body=message,from_email="1658441344@qq.com",
                            to=[email],reply_to=["1658441344@qq.com"])
        #email.attach_file('/images/weather_map.png')
        email.send()

        return HttpResponse("请查看邮箱，按照提示激活账户。"
                                "(验证链接只在一小时内有效).")
    return HttpResponse(status_code=200,content=True)

#用户点击邮箱链接,调用视图activate_user(),验证激活用户:
def activate_user(request,token):
    try:username=token_confirm.confirm_validate_token(token)
    except:
        return HttpResponse("抱歉，验证链接已过期，请重新注册。")
    try:user=User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponse("抱歉，当前用户不存在，请重新注册。")
    user.is_active=True
    user.save()
    return HttpResponse(status_code=200,content='Activate user successfully.')