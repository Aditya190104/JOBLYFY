from django.urls import path
from . import views, application_views, job_management

app_name = "jobs"
urlpatterns = [
    path(
        "jobs/<int:job_id>/status/",
        job_management.change_job_status,
        name="change_job_status",
    ),
    path(
        "jobs/<int:job_id>/questions/",
        job_management.screening_questions,
        name="screening_questions",
    ),
    path(
        "jobs/<int:job_id>/application/",
        application_views.application_start,
        name="application_start",
    ),
    path(
        "jobs/<int:job_id>/application/resume/",
        application_views.draft_resume,
        name="draft_resume",
    ),
    path(
        "jobs/<int:job_id>/application/discard/",
        application_views.discard_draft,
        name="discard_draft",
    ),
    path("", views.home, name="home"),
    path("jobs/", views.job_list, name="job_list"),
    path("locations/suggest/", views.location_suggestions, name="location_suggestions"),
    path("companies/<int:pk>/review/", views.company_review, name="company_review"),
    path("reviews/<int:pk>/remove/", views.remove_review, name="remove_review"),
    path("jobs/search/", views.search_jobs, name="search_jobs"),
    path("jobs/post/", views.post_job, name="post_job"),
    path("jobs/<int:job_id>/", views.job_detail, name="job_detail"),
    path("jobs/<int:job_id>/edit/", views.edit_job, name="edit_job"),
    path("jobs/<int:job_id>/toggle/", views.toggle_job, name="toggle_job"),
    path("jobs/<int:job_id>/apply/", views.apply_job, name="apply_job"),
    path("jobs/<int:job_id>/save/", views.save_job, name="save_job"),
    path("categories/", views.categories, name="categories"),
    path("categories/<int:pk>/", views.category_detail, name="category_detail"),
    path("companies/", views.companies, name="companies"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("about/", views.about, name="about"),
]
