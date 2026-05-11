from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('core',     '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Faculty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('employee_id',  models.CharField(db_index=True, max_length=20, unique=True)),
                ('designation',  models.CharField(blank=True, max_length=100)),
                ('joining_date', models.DateField(blank=True, null=True)),
                ('is_active',    models.BooleanField(default=True)),
                ('user',       models.OneToOneField(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='faculty_profile', to=settings.AUTH_USER_MODEL
                )),
                ('department', models.ForeignKey(
                    db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='core.branch'
                )),
            ],
            options={'verbose_name': 'Faculty', 'verbose_name_plural': 'Faculty Members'},
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('roll_number',    models.CharField(db_index=True, max_length=20, unique=True)),
                ('admission_year', models.IntegerField(default=2024)),
                ('is_active',      models.BooleanField(default=True)),
                ('user',    models.OneToOneField(
                    db_index=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_profile', to=settings.AUTH_USER_MODEL
                )),
                ('branch',  models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.branch')),
                ('year',    models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.year')),
                ('section', models.ForeignKey(db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.section')),
                ('class_teacher', models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='class_students', to='accounts.faculty'
                )),
                ('counsellor', models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='counselled_students', to='accounts.faculty'
                )),
            ],
            options={'verbose_name': 'Student', 'verbose_name_plural': 'Students'},
        ),
    ]
