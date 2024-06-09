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

from rest_framework.views import APIView
import itertools

from itertools import chain  
from operator import attrgetter 

serveAddress="http:127.0.0.1:8080"

#问卷填写界面：向前端传输问卷当前暂存的填写记录
class GetStoreFillView(APIView):
    def get(self, request, *args, **kwargs):  
        # 从查询参数中获取userName和surveyID   
        userName = kwargs.get('userName')  
        surveyID = kwargs.get('surveyID')   
        submissionID=kwargs.get('submissionID')  
        print(userName) 
        print(surveyID)
        print(submissionID)

        user=User.objects.get(username=userName)
        if user is None:
            return HttpResponse(content='User not found', status=404) 
        
        survey=Survey.objects.get(SurveyID=surveyID)
        if survey is None:
            return HttpResponse(content='Questionnaire not found', status=404)   
        
        #从问卷广场界面进入：查找该用户是否有该问卷未提交的填写记录
        if submissionID==-1:
            submission_query=Submission.objects.filter(Respondent=user,Survey=survey,Status='Unsubmitted')
            if submission_query.exists():
                submissionID=submission_query.first().SubmissionID  #找到未填写的记录
            else:       
                return HttpResponse(content='Submission not existed', status=404) 
        
        #从问卷管理界面进入：
        submission=Submission.objects.get(SubmissionID=submissionID)
        if submission is None:
            return HttpResponse(content='Submission not found', status=404) 
        
        Title=survey.Title
        Description=survey.Description
        category=survey.Category
        TimeLimit=survey.TimeLimit
        people=survey.QuotaLimit

        '''1.以下部分与问卷编辑界面的get函数类似，拿到题干'''
        '''2.拿到当前submissionID对应填写记录'''
        all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionID').all())
                                                    
        # 将迭代器转换为列表 (按QuestionNumber递增排序)
        all_questions_list = list(all_questionList_iterator)
        all_questions_list.sort(key=lambda x: x['QuestionNumber']) 

        questionList=[]

        #print(all_questions)
        for question in all_questions_list:
            if question["Category"]==1 or question["Category"]==2:    #选择题

                #该单选题的用户选项:当前问卷当前submission(如果用户未选，则找不到对应的答案记录)
                if question["Category"]==1:
                    print("#1")
                    optionAnswer=ChoiceAnswer.objects.get(Submission=submission,Question=question)  #只有一条记录
                    #用户未填该单选题
                    if optionAnswer is None:answer=-1
                    #用户填了这个单选题，有一条答案记录
                    else:answer=optionAnswer.ChoiceOptions.OptionID
                
                #该多选题的用户选项:当前问卷当前submission
                else:
                    print("#2")
                    optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question)#一或多条记录
                    #用户未填该多选题
                    if not optionAnswer_query.exists():answer=[-1]
                    #用户填了这个多选题，有一条/多条答案记录
                    answer=[]
                    for optionAnswer in optionAnswer_query:
                        answer.append(optionAnswer.ChoiceOptions.OptionID)

                optionList=[]
                #将所有选项顺序排列
                options_query=ChoiceOption.objects.filter(Question=question["QuestionID"]).order_by('OptionNumber')
                for option in options_query:
                    optionList.append({'content':option.Text,'optionNumber':option.OptionNumber,'isCorrect':option.IsCorrect,'optionID':option.OptionID})
                    print(option.Text)
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'optionCnt':question["OptionCnt"],
                                     'optionList':optionList,'Answer':answer})
                
            elif question["Category"]==3:                  #填空题
                print("#3")
                #该填空题的用户答案:有且仅有一条记录
                blankAnswer=BlankAnswer.objects.get(Submission=submission,Question=question)
                answer=blankAnswer.Content
                
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],
                                     'correctAnswer':question["CorrectAnswer"],'Answer':answer})

            elif question["Category"]==4:                  #评分题
                print("#4")
                #该评分题的用户答案:有且仅有一条记录
                ratingAnswer=RatingAnswer.objects.get(Submission=submission,Question=question)
                answer=ratingAnswer.Rate

                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'Answer':answer})


        print(survey.Title)
        print(survey.Description)
        data={'Title':survey.Title,'category':survey.Category,'people':survey.QuotaLimit,'TimeLimit':survey.TimeLimit,
              'description':survey.Description,'questionList':questionList}
        return data
        

#问卷填写界面：从前端接收用户的填写记录
def get_submission(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            surveyID=body['surveyID']    #问卷id
            status=body['status']  #填写记录状态
            submissionID=body['submissionID']   #填写记录ID
            username=body['usename']     #填写者
            submissionList=body['question']     #填写记录
            duration=body['duration']   

            survey=Survey.objects.get(SurveyID=surveyID)
            if survey is None:
                return HttpResponse(content='Questionnaire not found',status=404)
            
            user=User.objects.get(username=username)
            if user is None:
                return HttpResponse(content='User not found',status=404)

            #当前不存在该填写记录，创建：
            if submissionID==-1:
                submission=Submission.objects.create(Survey=survey,Respondent=user,
                                             SubmissionTime=timezone.now(),Status=status,
                                             Duration=duration)
            #已存在，删除填写记录的所有内容
            else:
                submission=Submission.objects.get(SubmissionID=submissionID)
                if submission is None:
                    return HttpResponse(content='Submission not found',status=404)
                
                #所有选择题的填写记录
                ChoiceAnswer_query=ChoiceAnswer.objects.filter(Submission=submission)
                for choiceAnswer in ChoiceAnswer_query:
                    choiceAnswer.delete()
                
                #所有填空题的填写记录
                BlankAnswer_query=BlankAnswer.objects.filter(Submission=submission)
                for BlankAnswer in BlankAnswer_query:
                    BlankAnswer.delete()
                
                #所有评分题的填写记录
                RatingAnswer_query=BlankAnswer.objects.filter(Submission=submission)
                for RatingAnswer in BlankAnswer_query:
                    RatingAnswer.delete()

            index=1
            for submissionItem in submissionList:
                questionID=submissionItem["questionID"]     #问题ID
                answer=submissionItem['value']        #用户填写的答案
                question = BaseQuestion.objects.get(QuestionID=questionID).select_subclasses()   #联合查询
                if question is None:
                    return HttpResponse(content='Question not found',status=404)
                
                if question["Category"]==1:     #单选题：Answer为选项ID
                    if answer==-1: continue       #返回-1，代表用户没填该单选题
                    option=ChoiceOption.objects.get(OptionID=answer)     #用户选择的选项
                    if option is None:
                        return HttpResponse(content="Option not found",status=404)
                    choiceAnswer=ChoiceAnswer.objects.create(Question=question,Submission=submission,ChoiceOptions=option)
                    choiceAnswer.save()

                elif question["Category"]==2:     #多选题：Answer为选项ID的数组
                    #为每个用户选择的选项，创建一条ChoiceAnswer记录
                    for optionID in answer:
                        if optionID==-1: continue       #返回[-1]，代表用户没填该多选题
                        option=ChoiceOption.objects.get(OptionID=optionID)     #用户选择的选项
                        if option is None:
                            return HttpResponse(content="Option not found",status=404)
                        choiceAnswer=ChoiceAnswer.objects.create(Question=question,Submission=submission,ChoiceOptions=option)
                        choiceAnswer.save()

                elif question["Category"]==3:     #填空题：answer为填写的内容
                    blankAnswer=BlankAnswer.objects.create(Question=question,Submission=submission,Content=answer)
                    choiceAnswer.save()
                
                else:       #评分题：answer为填写的内容
                    ratingAnswer=RatingAnswer.objects.create(Question=question,Submission=submission,Rate=answer)
                    ratingAnswer.save()
                
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)


#问卷编辑界面：向前端传输问卷设计内容
class GetQuestionnaireView(APIView):
    def get(self, request, survey_id, *args, **kwargs):  
        design = request.GET.get('design', 'false')  # 默认为'false'  
        design = design.lower() == 'true'  # 将字符串转换为布尔值  
        print(survey_id)
        survey=Survey.objects.get(SurveyID=survey_id)
        if survey is None:
            return HttpResponse(content='Questionnaire not found', status=400) 
        title=survey.Title
        catecory=survey.Category
        people=survey.QuotaLimit
        TimeLimit=survey.TimeLimit

        '''
        blank_questions = list(BlankQuestion.objects.filter(Survey=survey).values_list('id', 'QuestionNumber'))  
        choice_questions = list(ChoiceQuestion.objects.filter(Survey=survey).values_list('id', 'QuestionNumber'))  
        rating_questions = list(RatingQuestion.objects.filter(Survey=survey).values_list('id', 'QuestionNumber'))  

        # 将这些列表合并，并基于QuestionNumber进行排序  
        combined_questions = sorted(chain(blank_questions, choice_questions, rating_questions), key=lambda x: x[1])
        '''

        all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionNumber','QuestionID').all())
                                                    
        # 将迭代器转换为列表  
        all_questions_list = list(all_questionList_iterator)
        all_questions_list.sort(key=lambda x: x['QuestionNumber']) 

        questionList=[]

        #print(all_questions)
        for question in all_questions_list:
            if question["Category"]==1 or question["Category"]==2:    #选择题
                optionList=[]
                print("#1")
                #将所有选项顺序排列
                options_query=ChoiceOption.objects.filter(Question=question["QuestionID"]).order_by('OptionNumber')
                for option in options_query:
                    optionList.append({'content':option.Text,'optionNumber':option.OptionNumber,'isCorrect':option.IsCorrect,'optionID':option.OptionID})
                    print(option.Text)
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'optionCnt':question["OptionCnt"],
                                     'optionList':optionList})
                
            elif question["Category"]==3:                  #填空题
                print("#3")
                
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'correctAnswer':question["CorrectAnswer"]})
                print(question["Category"],question["Text"],question["QuestionID"],question["IsRequired"],question["Score"],question["CorrectAnswer"])

            elif question["Category"]==4:                  #评分题
                print("#4")
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"]})

        
        print(survey.Title)
        print(survey.Description)
        data={'Title':survey.Title,'category':survey.Category,'people':survey.QuotaLimit,'TimeLimit':survey.TimeLimit,
              'description':survey.Description,'questionList':questionList}
        
        return JsonResponse(data, status=200)


#问卷编辑界面：从前端接收问卷的设计内容
def save_qs_design(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            surveyID=body['surveyID']    #问卷id
            title=body['title']  #问卷标题
            catecory=body['category']   #问卷类型（普通0、投票1、报名2、考试3）
            isOrder=body['isOrder'] #是否顺序展示（考试问卷）
            people=body['people']   #报名人数（报名问卷）
            timelimit=body['timeLimit']
            username=body['userName']   #创建者用户名
            description=body['description'] #问卷描述
            Is_released=body['Is_released'] #保存/发布

            questionList=body['questionList']   #问卷题目列表
            user=User.objects.get(username=username)
            if user is None:        
                return HttpResponse(content='User not found', status=400) 

            #当前不存在该问卷，创建：
            if surveyID==-1:
                survey=Survey.objects.create(Owner=user,Title=title,
                                             Description=description,Is_released=Is_released,
                                             Is_open=False,Is_deleted=False,Category=catecory,
                                             TotalScore=0,TimeLimit=timelimit,IsOrder=isOrder,QuotaLimit=people
                                            )
            #已有该问卷的编辑记录
            else:
                survey=Survey.objects.get(SurveyID=surveyID)
                survey.Is_released=Is_released
                if survey is None:
                    return HttpResponse(content='Questionnaire not found', status=400) 
                #该问卷的所有选择题
                choiceQuestion_query=ChoiceQuestion.objects.filter(Survey=survey)
                for choiceQuestion in choiceQuestion_query:
                    #删除该选择题的所有选项
                    choiceOption_query=ChoiceOption.objects.filter(Question=choiceQuestion)
                    for choiceOption in choiceOption_query:
                        choiceOption.delete()
                    choiceQuestion.delete()

                #删除该问卷的所有填空题
                blankQuestion_query=BlankQuestion.objects.filter(Survey=survey)
                for blankQuestion in blankQuestion_query:
                    blankQuestion.delete()
                
                #删除该问卷的所有评分题
                ratingQuestion_query=RatingQuestion.objects.filter(Survey=survey)
                for ratingQuestion in ratingQuestion_query:
                    ratingQuestion.delete()

            index=1
            print(questionList)
            for question in questionList:
                print(question["type"])
                if question["type"]==1 or question["type"]==2:        #单选/多选
                    print(question)
                    print(question["question"])
                    print(question["isNecessary"])
                    print(question["score"])
                    print(index,question["optionCnt"])
                    print(question["type"])
                    optionList=question['optionList']
                    survey=Survey.objects.get(SurveyID=surveyID)
                    if survey is None:
                        return HttpResponse(content="hello",status=100)
                    print(survey.SurveyID)
                    question=ChoiceQuestion.objects.create(Survey=survey,Text=question["question"],IsRequired=question["isNecessary"],
                                                               QuestionNumber=index,Score=question["score"],Category=question["type"],
                                                               OptionCnt=question["optionCnt"])
                    question.save()
                    #所有选项:
                    jdex=1
                    for option in optionList:
                        print(option)
                        print(option['content'])
                        option=ChoiceOption.objects.create(Question=question,Text=option["content"],
                                                               IsCorrect=option["isCorrect"],OptionNumber=jdex)
                        option.save()
                        jdex=jdex+1
                
                elif question["type"]==3:                          #填空
                    print("*")
                    survey=Survey.objects.get(SurveyID=surveyID)
                    if survey is None:
                        return HttpResponse(content="hello",status=100)
                    print("#")
                    print("1")
                    print(question)
                    print(question["correctAnswer"])
                    print("2")
                    question=BlankQuestion.objects.create(Survey=survey,Text=question["question"],IsRequired=question["isNecessary"],
                                                              Score=question["score"],QuestionNumber=index,Category=question["type"],
                                                              CorrectAnswer=question["correctAnswer"])
                    print("#")
                    question.save()
                
                else:                                           #评分题
                    question=RatingQuestion.objects.create(Survey=survey,Text=question["question"],IsRequired=question["isNecessary"],
                                                              Score=question["score"],QuestionNumber=index,Category=question["type"])
                    question.save()
                index=index+1
            return HttpResponse(content='Questionnaire saved successfully', status=200) 
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)


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
                            submission.save()
            
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
                    qs.Is_released=False
                qs.save()

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
        data_list=[]

         # 使用 for 循环遍历 submission_query  
        with transaction.atomic():  # 你可以使用事务确保操作的原子性  
            for submission in submission_query:
                status=submission.Status
                if status=="Unsubmitted":
                    status_Chinese="未提交"
                elif status=="Submitted" or status=="Graded":
                    status_Chinese="已提交"
                else:
                    status_Chinese="已删除"
                data_list.append({'Title':submission.Survey.Title,'PublishDate':submission.Survey.PublishDate,
                                  'SurveyID':submission.Survey.SurveyID,'Category':submission.Survey.Category,
                                  'Description':submission.Survey.Description,'Status':status_Chinese,
                                  'SubmissionID':submission.SubmissionID})
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#问卷广场：检查投票/考试问卷
def check_qs(request,username,questionnaireId,type):
    user=User.objects.get(username=username)
    if user is None:
        return HttpResponse(content="User not found",status=404)
    qs=Survey.objects.get(SurveyID=questionnaireId)
    if qs is None:
        return HttpResponse(content="Questionnaire not found",status=404)
    
    #投票问卷:每个用户只可提交一次
    if qs.Category==1:
        submission_query=Submission.objects.filter(Respondent=user,Survey=qs)
        if submission_query.exists():
            submission=submission_query.first()
            if submission.Status=='Unsubmitted':
                data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
            elif submission.Status=='Submitted':
                data={'message':False,"content":"您完成投票，不可重复投票"}
            else:
                data={'message':False,"content":"当前问卷已被撤回"}
        else:
            data={'message':"True","content":"可以开始/继续填写"}
        return JsonResponse(data)
    
    #考试问卷：每个用户只可提交一次
    elif qs.Category==3:
        submission_query=Submission.objects.filter(Respondent=user,Survey=qs)
        if submission_query.exists():
            submission=submission_query.first()
            if submission.Status=='Unsubmitted':
                data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
            elif submission.Status=='Submitted':
                data={'message':False,"content":"您已完成当前考试"}
            else:
                data={'message':False,"content":"当前问卷已被撤回"}
        else:
            data={'message':"True","content":"可以开始/继续填写"}
        return JsonResponse(data)
    
    #报名问卷：超过人数，不可以再报名
    elif qs.Category==2:
        #检查是否超人数
        submission_query=Submission.objects.filter(Respondent=user,Survey=qs)
        currentCnt=Submission.objects.filter(Respondent=user,Survey=qs).count()
        if currentCnt>=qs.QuotaLimit:
            data={'message':False,"content":"当前报名人数已满"}
            return JsonResponse(data)

        #检查是否有未提交的填写记录
        unsubmitted_query=Submission.objects.filter(Respondent=user,Survey=qs,Status="Unsubmitted")
        if unsubmitted_query.exists():
            data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
        
        data={'message':"True","content":"可以开始/继续填写"}
        return JsonResponse(data)   

    #普通问卷
    else: 
        #检查是否有未提交的填写记录
        unsubmitted_query=Submission.objects.filter(Respondent=user,Survey=qs,Status="Unsubmitted")
        if unsubmitted_query.exists():
            data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
        else:
            data={'message':"True","content":"可以开始/继续填写"}

        return JsonResponse(data)   
    
#问卷广场：所有问卷
def get_all_released_qs(request):
    if(request.method=='GET'):
        qs_query=Survey.objects.filter(Is_released=True).order_by("-PublishDate")
        data_list=[]

        for survey in qs_query:
            reward=RewardOffering.objects.filter(Survey=survey).first()
            if reward is not None:
                data_list.append({'Title':survey.Title,'PostMan':survey.Owner.username,'PublishDate':survey.PublishDate,
                                  'SurveyID':survey.SurveyID,'categoryId':survey.Category,'Description':survey.Description,
                                  'Reward':reward.Zhibi,'HeadCount':reward.AvailableQuota})
            else:
                data_list.append({'Title':survey.Title,'PostMan':survey.Owner.username,'PublishDate':survey.PublishDate,
                                  'SurveyID':survey.SurveyID,'categoryId':survey.Category,'Description':survey.Description,
                                  'Reward':None,'HeadCount':None})
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


'''个人中心界面'''
#购买商店中的头像
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

            #修改纸币
            zhibi=body['money']
            user.zhibi=zhibi
            user.save()
            
            photos_data = json.loads(user.own_photos)  
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
            flag=body['flag']
            print(username)
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 

            #修改除头像外的其他信息
            if flag==1:
                email=body['email']
                password=body['password']
                print(email,password)
                user.email=email
                user.password=password
                user.save()
            
            #修改头像：
            elif flag==2:
                photonumber = body['photonumber']
                status = body['status']
                print(photonumber,status)
                user.set_array_element(photonumber,status)
                user.save()
            
            else:
                # 参数不正确或缺失  
                return JsonResponse({'error': 'Invalid or missing parameters'}, status=400)

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    data={"message":"True"}
    return JsonResponse(data)


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

#额外需要的包
import pandas as pd

#交叉分析
def cross_analysis(request,questionID1,questionID2):
    if request.method == 'GET':
        question1 = ChoiceQuestion.object.get(QuestionID=QuestionID1)
        question2 = ChoiceQuestion.object.get(QuestionID=QuestionID2)

        if questionID1 is None or questionID2 is None:
            return JsonResponse({'error': 'Missing QuestionID(s)'}, status=400)

        survey = question1.Survey

        results = []
        for options1 in question1.choice_options.all():
            for options2 in question2.choice_options.all():
                cnt = 0
                for submission in Submission.objects.filter(Survey=survey):
                    choice_answers = submission.choiceanswers_answers.all()
                    if choice_answers.filter(answers=options1).exists() and choice_answers.filter(answers=options2).exists():
                        cnt += 1
                results.append({
                    'content': f"{options1.Text}-{options2.Text}",
                    'cnt': cnt
                })

        return JsonResponse(results)

#下载表格
def download_submissions(request):
    if request.method == 'GET':
        survey_id = request.GET.get('surveyId')
        survey = Submission.objects.filter(Survey__SurveyID=survey_id).first().Survey

        submissions = Submission.objects.filter(Survey__SurveyID=survey_id, Status__in=['Submitted', 'Graded'])

        data = {
            '填写者': [],
            '提交时间': [],
        }

        if survey.Category == '3':
            data['分数'] = []

        questions = list(chain(
                BlankQuestion.objects.filter(Survey=survey),
                ChoiceQuestion.objects.filter(Survey=survey),
                RatingQuestion.objects.filter(Survey=survey)
            ))
        

        for question in questions:
            data[question.Text] = []

        for submission in submissions:
            data['填写者'].append(submission.Respondent.username)
            data['提交时间'].append(submission.SubmissionTime)

            if survey.Category == '3':
                data['分数'].append(submission.Score)

            for answer in submission.answers.all():
                if isinstance(answer, BlankAnswer):
                    data[answer.Question.Text].append(answer.Content)
                elif isinstance(answer, ChoiceAnswer):
                    choices = [chr(ord('A') + choice - 1) for choice in answer.selected_choices]
                    data[answer.Question.Text].append(', '.join(choices))
                elif isinstance(answer, RatingAnswer):
                    data[answer.Question.Text].append(answer.Rate)

        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="问卷填写情况.xlsx"'
        df.to_excel(response, index=False)

        return response
    return JsonResponse({'error': 'Invalid request method'}, status=405)

from django.db.models import Count, Sum, Q

def survey_statistics(request):
    if request.method=='GET':
        survey_id = request.GET.get('surveyId')
        survey = Survey.objects.get(id=survey_id)
        survey_stat = SurveyStatistic.objects.get(Survey=survey)
    
        #问卷基础信息
        stats = {
            'title': survey.title,
            'description': survey.description,
            'category': survey.category,
            'total_submissions': survey_stat.TotalResponses,
            'max_participants': survey.QuotaLimit if survey.QuotaLimit else None,
            'average_score': survey_stat.AverageScore,
            'questions_stats': []
        }
        
        questions = list(chain(
                BlankQuestion.objects.filter(Survey=survey),
                ChoiceQuestion.objects.filter(Survey=survey),
                RatingQuestion.objects.filter(Survey=survey)
            ))
        
        type_mapping = {
                'blankquestion': 3,
                'choicequestion': 1 if question.MaxSelectable == 1 else 2,
                'ratingquestion': 4
            }
    
        #题目信息
        for question in questions:
            question_type_num = type_mapping.get(question._meta.model_name, 0)
            
            q_stats = {
                'type': question_type_num,
                'question': question.text,
                'number': question.number,
                'is_required': question.is_required,
                'filled_count': Answer.objects.filter(question=question).count(),
                'score': question.score if survey.category == '3' else None,
                'correct_answer': None,
                'correct_count': 0,
                'options_stats': [],
                'rating_stats': [],
                'blank_stats': []
            }
    
        #答案信息
            if question._meta.model_name == 'choicequestion':
                correct_option_numbers = [option.number for option in question.choice_options.filter(is_correct=True)]
                q_stats['correct_answer'] = correct_option_numbers
                for option in question.choice_options.all():
                    option_stats = {
                        'number': option.number,
                        'is_correct': option.is_correct,
                        'content': option.Text,
                        'count': ChoiceAnswer.objects.filter(question=question, ChoiceOptions=option).count()
                    }
                    q_stats['options_stats'].append(option_stats)
    
                correct_submissions = set()
                for correct_number in correct_option_numbers:
                    submissions_with_correct_option = ChoiceAnswer.objects.filter(
                        question=question,
                        ChoiceOptions__number=correct_number
                    ).values_list('Submission', flat=True)
    
                    # 更新完全正确回答的提交集合
                    if not correct_submissions:
                        correct_submissions = set(submissions_with_correct_option)
                    else:
                        correct_submissions.intersection_update(submissions_with_correct_option)
    
                q_stats['correct_count'] = len(correct_submissions)
            
            elif question.type == 'ratingquestion':
                ratings = RatingAnswer.objects.filter(question=question).values('rate').annotate(count=Count('rate'))
                for rating in ratings:
                    q_stats['rating_stats'].append({
                        'rate': rating['rate'],
                        'count': rating['count']
                    })
    
            elif question.type == 'blankquestion':  
                answers = BlankAnswer.objects.filter(question=question).values('content').annotate(count=Count('content'))
                for answer in answers:
                    q_stats['blank_stats'].append({
                        'content': answer['content'],
                        'count': answer['count']
                    })
                    
            stats['questions_stats'].append(q_stats)
        return JsonResponse(stats)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

