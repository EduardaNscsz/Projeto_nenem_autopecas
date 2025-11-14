from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Produto, Transacao, Compra
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP


# ----------------------------- FINANCEIRO -----------------------------
def financeiro_pagina(request):
    transacoes = Transacao.objects.all().order_by('-data')
    entrada = Transacao.objects.filter(tipo='entrada').aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    saida = Transacao.objects.filter(tipo='saida').aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')

    if not isinstance(entrada, Decimal):
        entrada = Decimal(str(entrada))
    if not isinstance(saida, Decimal):
        saida = Decimal(str(saida))

    saldo = (entrada - saida).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return render(request, "controle/financeiro.html", {
        "transacoes": transacoes,
        "entrada": entrada,
        "saida": saida,
        "saldo": saldo
    })


# ----------------------------- LOGIN -----------------------------
def index(request):
    return render(request, "controle/index.html")


def login_view(request):
    return render(request, "controle/index.html")


def logar(request):
    if request.method == "POST":
        email = request.POST.get("email")
        senha = request.POST.get("senha")

        usuario = authenticate(username=email, password=senha)

        if usuario is None:
            messages.error(request, "E-mail ou senha incorretos.")
            return redirect('/')

        login(request, usuario)
        return redirect('/dashboard/')

    return redirect('/')


def logout_view(request):
    logout(request)
    return redirect("/")


# ----------------------------- CADASTRO -----------------------------
def controle_cadastro(request):
    if request.method == "POST":
        nome = request.POST.get("nome")
        cargo = request.POST.get("cargo")  # << ADICIONADO
        email = request.POST.get("email")
        senha = request.POST.get("senha")

        if User.objects.filter(username=email).exists():
            messages.error(request, "Esse e-mail já está cadastrado.")
            return redirect("/cadastro/")

        usuario = User.objects.create_user(
            username=email,
            email=email,
            password=senha,
            first_name=nome,
            last_name=cargo  # << SALVA O CARGO AQUI
        )

        login(request, usuario)
        return redirect("/dashboard/")

    return render(request, "controle/cadastro.html")


# ----------------------------- DASHBOARD -----------------------------
def dashboard(request):
    total_produtos = Produto.objects.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    total_vendas = Transacao.objects.filter(tipo='entrada').aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    total_compras = Transacao.objects.filter(tipo='saida').aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    saldo = (total_vendas - total_compras).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    ultimas_vendas = Transacao.objects.filter(tipo='entrada').order_by('-data')[:5]

    contexto = {
        'total_produtos': total_produtos,
        'total_vendas': total_vendas,
        'total_compras': total_compras,
        'saldo': saldo,
        'ultimas_vendas': ultimas_vendas,
    }

    return render(request, "controle/dashboard.html", contexto)


# ----------------------------- VENDAS -----------------------------
def vendas(request):
    produtos = Produto.objects.all().order_by('nome')
    vendas_recentes = Transacao.objects.filter(tipo='entrada').order_by('-data')[:20]
    total_vendido = Transacao.objects.filter(tipo='entrada').aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')

    if not isinstance(total_vendido, Decimal):
        total_vendido = Decimal(str(total_vendido))

    if request.method == "POST":
        produtos_ids = request.POST.getlist("produto_id[]")
        quantidades = request.POST.getlist("quantidade[]")
        precos = request.POST.getlist("preco_readonly[]")

        total_venda = Decimal('0.00')
        itens_registrados = []

        for i in range(len(produtos_ids)):
            pid = produtos_ids[i]
            try:
                qtd = int(quantidades[i]) if quantidades[i] else 0
            except ValueError:
                qtd = 0

            preco_text = precos[i] if i < len(precos) else '0'
            preco_text = preco_text.replace('.', '').replace(',', '.').strip() if preco_text else '0'
            try:
                preco = Decimal(preco_text)
            except Exception:
                preco = Decimal('0.00')

            if not pid or qtd <= 0 or preco <= 0:
                continue

            try:
                produto = Produto.objects.get(id=pid)
            except Produto.DoesNotExist:
                continue

            if produto.quantidade < qtd:
                messages.warning(request, f"Estoque insuficiente para {produto.nome}. Item ignorado.")
                continue

            produto.quantidade -= qtd
            produto.save()

            subtotal = (preco * Decimal(qtd)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_venda += subtotal
            itens_registrados.append(f"{qtd}x {produto.nome} (R$ {subtotal:.2f})")

        if total_venda > Decimal('0.00'):
            descricao_venda = "Venda - " + ", ".join(itens_registrados)
            Transacao.objects.create(
                tipo='entrada',
                descricao=descricao_venda,
                valor=total_venda,
                data=timezone.now()
            )
            messages.success(request, f"Venda registrada com sucesso! Total R$ {total_venda:.2f}")
        else:
            messages.warning(request, "Nenhuma venda válida foi registrada.")

        return redirect("vendas")

    contexto = {
        "produtos": produtos,
        "vendas_recentes": vendas_recentes,
        "total_vendido": total_vendido
    }

    return render(request, "controle/vendas.html", contexto)


# ----------------------------- COMPRAS -----------------------------
def compras(request):
    produtos = Produto.objects.all().order_by('nome')

    if request.method == "POST":
        fornecedor = request.POST.get("fornecedor")
        nomes = request.POST.getlist("produto_nome[]")
        quantidades = request.POST.getlist("quantidade[]")
        precos = request.POST.getlist("preco[]")
        adicionar_estoque = request.POST.get("adicionar_estoque")

        if not fornecedor or not nomes:
            messages.error(request, "Preencha o fornecedor e pelo menos um produto.")
            return redirect("compras")

        total_compra = Decimal('0.00')

        for i in range(len(nomes)):
            nome = nomes[i].strip()
            try:
                qtd = int(quantidades[i]) if quantidades[i] else 0
            except ValueError:
                qtd = 0
            preco_text = precos[i] if precos[i] else '0'
            preco_text = preco_text.replace('.', '').replace(',', '.').strip()
            try:
                preco = Decimal(preco_text)
            except Exception:
                preco = Decimal('0.00')

            subtotal = (preco * Decimal(qtd)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if not nome or qtd <= 0 or preco <= 0:
                continue

            produto, criado = Produto.objects.get_or_create(
                nome=nome,
                defaults={'valor': preco, 'quantidade': 0}
            )

            produto.valor = preco
            if adicionar_estoque == "sim":
                produto.quantidade += qtd
            produto.save()

            Compra.objects.create(
                fornecedor=fornecedor,
                produto=produto,
                quantidade=qtd,
                valor_total=subtotal
            )

            Transacao.objects.create(
                tipo='saida',
                descricao=f"Compra de {qtd}x {produto.nome} de {fornecedor}",
                valor=subtotal,
                data=timezone.now()
            )

            total_compra += subtotal

        if adicionar_estoque == "sim":
            messages.success(request, f"Compra registrada e estoque atualizado! Total gasto: R$ {total_compra:.2f}")
        else:
            messages.success(request, f"Compra registrada sem atualizar estoque. Total gasto: R$ {total_compra:.2f}")

        return redirect("compras")

    total_gasto = Compra.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
    total_itens = Compra.objects.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    ultima_compra = Compra.objects.last()
    ultima_compra_data = ultima_compra.data.strftime('%d/%m/%Y %H:%M') if ultima_compra else "—"
    compras = Compra.objects.all().order_by('-data')

    contexto = {
        'produtos': produtos,
        'compras': compras,
        'total_gasto': f"{total_gasto:.2f}",
        'total_itens': total_itens,
        'ultima_compra': ultima_compra_data,
    }

    return render(request, "controle/compras.html", contexto)


# ----------------------------- ESTOQUE -----------------------------
def estoque_pagina(request):
    if request.method == "POST" and "add" in request.POST:
        Produto.objects.create(
            nome=request.POST["nome"],
            quantidade=int(request.POST["quantidade"]),
            valor=float(request.POST["valor"]),
        )
        messages.success(request, "Produto adicionado com sucesso!")
        return redirect('/estoque/')

    if request.method == "POST" and "edit" in request.POST:
        produto = get_object_or_404(Produto, id=request.POST["id"])
        produto.nome = request.POST["nome"]
        produto.quantidade = int(request.POST["quantidade"])
        produto.valor = float(request.POST["valor"])
        produto.save()
        messages.success(request, "Produto atualizado com sucesso!")
        return redirect('/estoque/')

    if request.method == "POST" and "delete" in request.POST:
        produto_id = request.POST.get("id")
        produto = get_object_or_404(Produto, id=produto_id)
        nome = produto.nome
        produto.delete()
        messages.success(request, f"Produto '{nome}' removido do estoque!")
        return redirect('/estoque/')

    produtos = Produto.objects.all().order_by('id')
    editar_id = request.GET.get("editar")
    produto_editar = get_object_or_404(Produto, id=editar_id) if editar_id else None

    return render(
        request,
        "controle/estoque.html",
        {"produtos": produtos, "produto_editar": produto_editar}
    )


# ----------------------------- OUTRAS TELAS -----------------------------
def fiscal(request):
    ultimas_vendas = Transacao.objects.filter(tipo='entrada').order_by('-data')[:5]
    return render(request, "controle/fiscal.html", {"ultimas_vendas": ultimas_vendas})


def financeiro(request):
    return financeiro_pagina(request)


def stock(request):
    return render(request, "controle/stock.html")


# ----------------------------- USUÁRIOS -----------------------------
def usuarios(request):
    usuarios_lista = User.objects.all().order_by('id')
    return render(request, "controle/usuarios.html", {"usuarios": usuarios_lista})


def excluir_usuario(request, id):
    usuario = get_object_or_404(User, id=id)
    usuario.delete()
    messages.success(request, "Usuário removido com sucesso!")
    return redirect("usuarios")
