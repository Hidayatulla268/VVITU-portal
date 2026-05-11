from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Branch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(max_length=10, unique=True)),
            ],
            options={'verbose_name_plural': 'Branches', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Year',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('year', models.IntegerField(
                    choices=[(1,'I Year'),(2,'II Year'),(3,'III Year'),(4,'IV Year')],
                    unique=True
                )),
            ],
            options={'ordering': ['year']},
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=5)),
                ('branch', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.branch')),
                ('year',   models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.year')),
            ],
            options={'ordering': ['branch', 'year', 'name']},
        ),
        migrations.AddConstraint(
            model_name='section',
            constraint=models.UniqueConstraint(fields=['name','branch','year'], name='unique_section'),
        ),
        # Faculty placeholder — real model added in accounts 0002
        # Subject needs Faculty FK so we create it after accounts 0002
        # For now create Exam, AcademicCalendar, QuestionPaper stubs that
        # don't need Faculty yet. Subject/Timetable/Attendance added in 0002.
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('exam_type', models.CharField(
                    choices=[('mid1','Mid Term 1'),('mid2','Mid Term 2'),('final','Semester Final'),('supply','Supplementary')],
                    default='mid1', max_length=10
                )),
                ('semester', models.IntegerField(db_index=True)),
                ('date', models.DateField(blank=True, null=True)),
                ('year',   models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.year')),
                ('branch', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.branch')),
            ],
            options={'ordering': ['-date']},
        ),
        migrations.CreateModel(
            name='AcademicCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title',       models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('date',        models.DateField(db_index=True)),
                ('event_type',  models.CharField(
                    choices=[('holiday','Holiday'),('exam','Examination'),('event','College Event'),
                             ('deadline','Deadline'),('other','Other')],
                    db_index=True, default='other', max_length=15
                )),
                ('branch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.branch')),
                ('year',   models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.year')),
            ],
            options={'ordering': ['date']},
        ),
    ]
