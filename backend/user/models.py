from django.db import models

# Create your models here.
class User(models.Model):
    username = models.CharField(primary_key=True, unique=True, max_length=50)
    password = models.CharField(max_length=25)
    email = models.EmailField(unique=True, max_length=100)
    CreateDate = models.DateTimeField(auto_now_add=True)
    isActive=models.BooleanField(default=False)
    Zhibi=models.IntegerField(default=0)
    own_photos=models.TextField(default=json.dumps([0] * 18))

    def set_array_element(self, index, value):
        # 确保索引在有效范围内  
        if 0 <= index < 18:  
            photos_data = json.loads(self.own_photos)  
            photos_data[index] = value  
            self.own_photos = json.dumps(photos_data)  
            self.save()  
    
    def get_array_element(self, index):  
        # 确保索引在有效范围内  
        if 0 <= index < 18:  
            photos_data = json.loads(self.own_photos)  
            return photos_data[index]  
        return -1
    
    #获取当前正在使用的头像编号(默认为0，1是已购买，2是正在使用)
    def get_used_element(self):
        photos_data = json.loads(self.own_photos)
        for i in range(0,18):
            if(photos_data[i]==2): return i
        return -1

class Survey(models.Model):
    SurveyID = models.AutoField(primary_key=True)
    Owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='surveys')
    Title = models.CharField(max_length=200)
    Description = models.TextField(max_length=500, blank=True)
    Is_released = models.BooleanField(default=False)
    Is_open = models.BooleanField(default=True)
    PublishDate = models.DateTimeField()
    #0 是普通问卷，1是投票问卷，2是报名问卷，3是考试问卷
    Category = models.IntegerField(default=0)   
    TotalScore = models.IntegerField(null=True, blank=True)
    TimeLimit = models.IntegerField(null=True, blank=True)
    IsOrder = models.BooleanField(default=True)
    QuotaLimit = models.IntegerField(null=True, default=False)

class BaseQuestion(models.Model):
    QuestionID = models.AutoField(primary_key=True)
    Survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='%(class)s_questions')
    Text = models.TextField(max_length=500)
    IsRequired = models.BooleanField(default=True)
    Score = models.IntegerField(null=True, blank=True)
    Number = models.IntegerField()

    class Meta:
        abstract = True

class BlankQuestion(BaseQuestion):
    pass

class ChoiceQuestion(BaseQuestion):
    HasOtherOption = models.BooleanField(default=False)
    MaxSelectable = models.IntegerField(default=1)

class ChoiceOption(models.Model):
    OptionID = models.AutoField(primary_key=True)
    Question = models.ForeignKey(ChoiceQuestion, on_delete=models.CASCADE, related_name='choice_options')
    Text = models.CharField(max_length=200)
    IsCorrect = models.BooleanField(default=False)
    
class OtherOption(models.Model):
    TextIsRequired = models.BooleanField(default=True)
    Text = models.TextField(max_length=500)

class RatingQuestion(BaseQuestion):
    MinRating = models.IntegerField(default=1)
    MinText = models.TextField(max_length=500)
    MaxRating = models.IntegerField(default=5)
    MaxText = models.TextField(max_length=500)

class Answer(models.Model):
    AnswerID = models.AutoField(primary_key=True)
    Submission = models.ForeignKey('Submission', on_delete=models.CASCADE, related_name='%(class)s_answers')

    class Meta:
        abstract = True

class BlankAnswer(Answer):
    Question = models.ForeignKey(BlankQuestion, on_delete=models.CASCADE)
    Content = models.TextField(max_length=500)
    GivenScore = models.IntegerField(null=True, blank=True)

class ChoiceAnswer(Answer):
    Question = models.ForeignKey(ChoiceQuestion, on_delete=models.CASCADE)
    ChoiceOptions = models.ForeignKey(ChoiceOption, on_delete=models.CASCADE)

class RatingAnswer(Answer):
    Question = models.ForeignKey(RatingQuestion, on_delete=models.CASCADE)
    Rate = models.IntegerField(null=True, blank=True)

class Submission(models.Model):
    SubmissionID = models.AutoField(primary_key=True)
    Survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='submissions')
    Respondent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    SubmissionTime = models.DateTimeField(auto_now_add=True)
    Status = models.CharField(max_length=20, choices=[('Unsubmitted', 'Unsubmitted'), ('Submitted', 'Submitted'), ('Graded', 'Graded')])
    Duration = models.DurationField(null=True, blank=True)

class SurveyStatistic(models.Model):
    StatisticID = models.AutoField(primary_key=True)
    Survey = models.OneToOneField(Survey, on_delete=models.CASCADE, related_name='statistics')
    TotalResponses = models.IntegerField(default=0)
    GradedResponses = models.IntegerField(default=0)
    AverageScore = models.FloatField(null=True, blank=True)

class Template(models.Model):
    TemplateID = models.AutoField(primary_key=True)
    Name = models.CharField(max_length=200)
    Type = models.CharField(max_length=50)
    DefaultQuestionsJSON = models.JSONField()
    Description = models.TextField(max_length=500, blank=True)

class RewardOffering(models.Model):
    RewardID = models.AutoField(primary_key=True)
    Survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='rewards')
    Description = models.TextField()
    Zhibi = models.IntegerField()#一份
    AvailableQuota = models.IntegerField()#份数

class UserRewardRecord(models.Model):
    RecordID = models.AutoField(primary_key=True)
    Respondent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='receive_records')
    RewardOffering = models.ForeignKey(RewardOffering, on_delete=models.CASCADE, related_name='rewards')
    Survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='Survey_rewards')
    Zhibi = models.IntegerField()
    RedemptionDate = models.DateField()

#Submission状态变化时更新SurveyStatistic
@receiver(pre_save, sender=Submission)
def update_survey_statistic_on_submission_status_change(sender, instance, **kwargs):
    try:
        old_instance = Submission.objects.get(pk=instance.SubmissionID)
    except Submission.DoesNotExist:
        return  # New record, skip

    if old_instance.Status == 'Unsubmitted' and instance.Status == 'Submitted':
        survey_statistic = instance.Survey.statistics
        survey_statistic.TotalResponses += 1
        survey_statistic.save(update_fields=['TotalResponses'])

    elif old_instance.Status == 'Submitted' and instance.Status == 'Graded':
        survey_statistic = instance.Survey.statistics
        graded_responses = survey_statistic.GradedResponses + 1
        new_average_score = (survey_statistic.AverageScore * survey_statistic.GradedResponses + instance.Score) / graded_responses
        survey_statistic.AverageScore = new_average_score
        survey_statistic.GradedResponses = graded_responses
        survey_statistic.save(update_fields=['AverageScore', 'GradedResponses'])

#UserRewardRecord创建时同步Zhibi字段
@receiver(post_save, sender=UserRewardRecord)
def synchronize_zhibi_on_user_reward_record_creation(sender, instance, created, **kwargs):
    if created:
        instance.Zhibi = instance.RewardOffering.Zhibi
        instance.Respondent.Zhibi += instance.Zhibi
        instance.Respondent.save(update_fields=['Zhibi'])

#Survey发布状态变化时更新PublishDate和计算总分
@receiver(pre_save, sender=Survey)
def handle_survey_release_and_calculate_totalscore(sender, instance, **kwargs):
    try:
        old_instance = Survey.objects.get(pk=instance.SurveyID)
    except Survey.DoesNotExist:
        return  # New record, skip

    if old_instance.Status == 'Unpublished' and instance.Status == 'Published':
        # Update PublishDate to current time
        instance.PublishDate = now()
        
        # Calculate TotalScore by summing up scores of related BlankQuestion and ChoiceQuestion
        total_score = (
            instance.blankQuestion_questions.filter(Score__isnull=False).aggregate(score_sum=Sum('Score'))['score_sum'] or 0
            + instance.choiceQuestion_questions.filter(Score__isnull=False).aggregate(score_sum=Sum('Score'))['score_sum'] or 0
        )
        instance.TotalScore = total_score
        
        # Save with updated PublishDate and TotalScore
        instance.save(update_fields=['PublishDate', 'TotalScore'])

#创建Survey时自动创建对应Statistic表
@receiver(post_save, sender=Survey)
def create_survey_statistic(sender, instance, created, **kwargs):
    if created:  # Only create SurveyStatistic when a new Survey is created
        SurveyStatistic.objects.create(Survey=instance)