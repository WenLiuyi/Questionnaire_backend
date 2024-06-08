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
from django.db import transaction 

serveAddress="http:127.0.0.1:8080"



#创建者的填写记录
def delete_filled_qs(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            submissionID=body
            if submissionID is None:
                return JsonResponse({'error': 'No ID provided'}, status=400) 
            submission=Submission.objects.filter(SubmissionID=submissionID).first()     #对应填写记录
            submission.delete()

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def update_or_delete_released_qs(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            flag=body['flag']

        #创建者删除已发布的问卷(将问卷状态改为Is_deleted=True)
        #所有该问卷填写者处，该问卷的状态修改为已删除；填写者刷新问卷管理界面，保留被删除项，但无法继续填写
            if flag==1:
                qsID=body['id']
                if qsID is None:
                    return JsonResponse({'error': 'No ID provided'}, status=400) 
                qs=Survey.objects.filter(SurveyID=qsID).first()     #对应问卷
                qs.Is_deleted=True

                submission_query=Submission.objects.filter(Survey=qs)   #该问卷的所有填写记录
            
                # 使用 for 循环遍历 submission_query  
                with transaction.atomic():  # 你可以使用事务确保操作的原子性  
                    for submission in submission_query:  
                        #该填写已提交：状态不变
                        #该填写未提交：填写状态改为'Deleted'(已被创建者删除)
                        if submission.Status=='Unsubmitted':
                            submission.Status='Deleted'
            
            #更新创建
            else:
                qsID=body['id']
                if qsID is None:
                    return JsonResponse({'error': 'No ID provided'}, status=400) 
                qs=Survey.objects.filter(SurveyID=qsID).first()     #对应问卷

                #当前未发布，改为发布状态：
                if qs.Is_released==False:
                    qs.Is_released=True
                
                #当前已发布，撤回
                else:
                    qs.Is_released=True

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)


#删除未发布的问卷(直接从数据库移除)
def delete_unreleased_qs(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            qsID=body
            if qsID is None:
                return JsonResponse({'error': 'No ID provided'}, status=400) 
            qs=Survey.objects.filter(SurveyID=qsID).first()
            if qs is None:  
                return JsonResponse({'error': 'No questionnaire found with the given ID'}, status=404)
            qs.delete()

            data={'message':'True'}
            return JsonResponse(data)
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#当前用户已创建未发布的问卷
def get_drafted_qs(request,username):
    if(request.method=='GET'):
        user=User.objects.get(username=username)
        qs_query=Survey.objects.filter(Owner=user,Is_released=False)
        data_list=[{'Title':survey.Title,'PublishDate':survey.PublishDate,'SurveyID':survey.SurveyID,'Category':survey.Category} for survey in qs_query]
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#当前用户发布的问卷
def get_released_qs(request,username):
    if(request.method=='GET'):
        user=User.objects.get(username=username)
        qs_query=Survey.objects.filter(Owner=user,Is_released=True,Is_deleted=False)    #不显示已删除问卷
        data_list=[{'Title':survey.Title,'PublishDate':survey.PublishDate,'SurveyID':survey.SurveyID,'Category':survey.Category,'Description':survey.Description} for survey in qs_query]
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#当前用户的填写记录(包括被创建者删除的问卷的填写记录)
def get_filled_qs(request,username):
    if(request.method=='GET'):
        user=User.objects.get(username=username)
        submission_query=Submission.objects.filter(Respondent=user)
        data_list=[{'Title':submission.Survey.Title,'PublishDate':submission.Survey.PublishDate,'SurveyID':submission.Survey.SurveyID,'Category':submission.Survey.Category,'Description':submission.Survey.Description} for submission in submission_query]
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
    
#问卷广场：所有问卷
def get_all_released_qs(request):
    if(request.method=='GET'):
        qs_query=Survey.objects.filter(Is_released=True).order_by("-PublishDate")
        data_list=[]

        for survey in qs_query:
            reward=RewardOffering.objects.filter(Survey=survey).first()
            if reward is not None:
                data_list.append({'Title':survey.Title,'PostMan':survey.Owner.username,'PublishDate':survey.PublishDate,'SurveyID':survey.SurveyID,'categoryId':survey.Category,'Description':survey.Description,'Reward':reward.TotalZhibi,'HeadCount':reward.AvailableQuota})
            else:
                data_list.append({'Title':survey.Title,'PostMan':survey.Owner.username,'PublishDate':survey.PublishDate,'SurveyID':survey.SurveyID,'categoryId':survey.Category,'Description':survey.Description,'Reward':None,'HeadCount':None})
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


'''个人中心界面'''
#修改商店中的头像
def modify_photo_in_shop(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            username=body['username']
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 
            
            photonumber = body['photonumber']
            status = body['status']

            #修改头像
            photonumber = body['photonumber']
            status = body['status']
            user.set_array_element(photonumber,status)

            photos_data = json.loads(user.own_photos)  
            ownphotos=photos_data
            data={'ownphotos':photos_data}
            return JsonResponse(data)

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#获取个人信息
def get_user_info(request,username):
    if(request.method=='GET'):
        try:
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 
            
            photo=user.get_used_element()
            data={'password':user.password,'email':user.email,'zhibi':user.zhibi,'photo':photo}
            return JsonResponse(data)
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#修改个人信息
def modify_user_info(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            username=body['username']
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 

            #修改除头像外的其他信息
            if 'email' in request.POST and 'password' in request.POST and 'zhibi' in request.POST:
                email=body['email']
                password=body['password']
                zhibi=body['zhibi']

                user.email=email
                user.password=password
                user.zhibi=zhibi

                data={'message':'True'}
                return JsonResponse(data)
            
            #修改头像：
            elif 'photonumber' in request.POST and 'status' in request.POST:
                photonumber = body['photonumber']
                status = body['status']
                user.set_array_element(photonumber,status)
            
            else:
                # 参数不正确或缺失  
                return JsonResponse({'error': 'Invalid or missing parameters'}, status=400)

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)


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
    return HttpResponse(status=200,content=True)

def send_registration_email(request):
    if(request.method=='POST'):
        body=json.loads(request.body)
        username=body['username']
        password=body['password']
        email=body['email']


        if(email==False):
            user_queryset=User.objects.filter(username=username)
            user=user_queryset.first()
            #return HttpResponse(status=200,content=username)
            if not user_queryset.exists():
                data={'message':"1"}
                return JsonResponse(data)
                #return HttpResponse(status=200,content="1")
            elif(password!=user.password):
                data={'message':"2"}
                return JsonResponse(data)
                #return HttpResponse(status=200,content="2")
            else:
                photos_data = json.loads(user.own_photos)  
                data={
                    'message':"0",
                    'username':user.username,
                    'password':user.password,
                    'email':user.email,
                    'ownphotos':photos_data,
                    'zhibi':user.zhibi,
                }
            return JsonResponse(data)

        user1=User.objects.filter(username=username)
        if user1.exists():
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
        message=("Hello,"+username+"! 欢迎注册“纸翼传问”!\n"
                     +"请点击以下链接，以激活新账户:\n"
                     +serveAddress+url+token)

        email=EmailMessage(subject=subject,body=message,from_email="1658441344@qq.com",
                            to=[email],reply_to=["1658441344@qq.com"])
        #email.attach_file('/images/weather_map.png')
        email.send()

        return HttpResponse("请查看邮箱，按照提示激活账户。"
                                "(验证链接只在一小时内有效).")
    return HttpResponse(status=200,content=True)

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
    return HttpResponse(status=200,content=True)