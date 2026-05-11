from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core',     '0002_subject_timetable_attendance_result_questionpaper'),
        ('accounts', '0002_student_faculty'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResultRelease',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('released',    models.BooleanField(default=False)),
                ('released_at', models.DateTimeField(blank=True, null=True)),
                ('email_sent',  models.BooleanField(default=False)),
                ('exam', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='release', to='core.exam'
                )),
                ('released_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='accounts.user'
                )),
            ],
            options={'verbose_name': 'Result Release'},
        ),
    ]
