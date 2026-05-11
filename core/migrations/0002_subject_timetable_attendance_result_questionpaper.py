from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core',     '0001_initial'),
        ('accounts', '0002_student_faculty'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name',     models.CharField(max_length=150)),
                ('code',     models.CharField(db_index=True, max_length=20, unique=True)),
                ('semester', models.IntegerField(
                    choices=[(i, f'Sem {i}') for i in range(1, 9)],
                    db_index=True
                )),
                ('credits', models.IntegerField(default=3)),
                ('is_lab',  models.BooleanField(default=False)),
                ('branch',   models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.branch')),
                ('year',     models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.year')),
                ('faculty',  models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='subjects', to='accounts.faculty'
                )),
            ],
            options={'ordering': ['branch', 'year', 'name']},
        ),
        migrations.CreateModel(
            name='Timetable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('day',    models.CharField(
                    choices=[('Monday','Monday'),('Tuesday','Tuesday'),('Wednesday','Wednesday'),
                             ('Thursday','Thursday'),('Friday','Friday'),('Saturday','Saturday')],
                    db_index=True, max_length=10
                )),
                ('period',     models.IntegerField(choices=[(i, f'Period {i}') for i in range(1, 9)])),
                ('start_time', models.TimeField(blank=True, null=True)),
                ('end_time',   models.TimeField(blank=True, null=True)),
                ('section', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='timetable_entries', to='core.section'
                )),
                ('subject', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.subject')),
                ('faculty', models.ForeignKey(
                    db_index=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='accounts.faculty'
                )),
            ],
            options={'ordering': ['day', 'period']},
        ),
        migrations.AddConstraint(
            model_name='timetable',
            constraint=models.UniqueConstraint(fields=['section','day','period'], name='unique_timetable_slot'),
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('date',          models.DateField(db_index=True)),
                ('status',        models.CharField(choices=[('P','Present'),('A','Absent')], default='A', max_length=1)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_records', to='accounts.student'
                )),
                ('timetable_entry', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.timetable'
                )),
                ('marked_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='accounts.faculty'
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(
                fields=['student','timetable_entry','date'], name='unique_attendance'
            ),
        ),
        migrations.CreateModel(
            name='Result',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('marks_obtained', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('max_marks',      models.DecimalField(decimal_places=2, default=100, max_digits=5)),
                ('grade',          models.CharField(blank=True, max_length=3)),
                ('student', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='results', to='accounts.student'
                )),
                ('exam',    models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.exam')),
                ('subject', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, to='core.subject')),
            ],
        ),
        migrations.AddConstraint(
            model_name='result',
            constraint=models.UniqueConstraint(fields=['student','exam','subject'], name='unique_result'),
        ),
        migrations.CreateModel(
            name='QuestionPaper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title',       models.CharField(max_length=200)),
                ('year',        models.IntegerField(db_index=True)),
                ('semester',    models.IntegerField(db_index=True)),
                ('file',        models.FileField(upload_to='question_papers/')),
                ('upload_date', models.DateField(auto_now_add=True)),
                ('subject', models.ForeignKey(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='question_papers', to='core.subject'
                )),
                ('uploaded_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='accounts.faculty'
                )),
            ],
            options={'ordering': ['-year', '-semester']},
        ),
    ]
