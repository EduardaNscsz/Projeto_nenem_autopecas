from django.urls import path
from . import views

urlpatterns = [
    # LOGIN
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logar/', views.logar, name='logar'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.controle_cadastro, name='controle_cadastro'),

    # DASHBOARD
    path('dashboard/', views.dashboard, name='dashboard'),

    # OUTRAS TELAS
    path('vendas/', views.vendas, name='vendas'),
    path('compras/', views.compras, name='compras'),
    path('fiscal/', views.fiscal, name='fiscal'),
    path('financeiro/', views.financeiro, name='financeiro'),
    path('stock/', views.stock, name='stock'),

    # USUÁRIOS
    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/excluir/<int:id>/', views.excluir_usuario, name='excluir_usuario'),

    # ESTOQUE
    path('estoque/', views.estoque_pagina, name='estoque'),
]
