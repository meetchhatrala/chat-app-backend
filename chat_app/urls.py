from django.urls import path
from chat_app import views

urlpatterns = [
    path('csrf/', views.set_csrf_cookie, name="set_csrf_cookie"),

    path('search/', views.search, name="search"),
    path('friend-request/', views.friend_request, name="friend_request"),
    path('handle-request/', views.handle_request, name="handle_request"),

    path('get-connections/', views.get_connections, name="get_connections"),
    path('get-chats/', views.get_chats, name="get_chats"),
    path('create-group/', views.create_group, name="create_group"),

    path('get-notifications/', views.get_notifications, name="get_notifications"),

    path('handle-group-request/', views.handle_group_request, name="handle_group_request"),
    
    path('get-members/<int:group_id>/', views.get_members, name="get_members"),
    path('remove-members/<int:group_id>/', views.remove_members, name="remove_members"),
    path('add-members/<int:group_id>/', views.add_members, name="add_members"),

    path('get-user-details/<int:id>/', views.get_user_details, name="get_user_details"),
    path('get-group-details/<int:id>/', views.get_group_details, name="get_group_details"),
    path('remove-connection/', views.remove_connection, name="remove_connection"),


    path('get-account-details/', views.get_account_details, name="get_account_details"),
    path('update-account-details/', views.update_account_details, name="update_account_details"),

    path('login/', views.login, name="login"),
    path('signup/', views.signup, name="signup"),
]
