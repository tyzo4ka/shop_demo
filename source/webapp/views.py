from django.http import HttpResponseRedirect
from django.shortcuts import reverse, redirect, get_object_or_404, render

from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from webapp.forms import BasketOrderCreateForm, ManualOrderForm, OrderProductForm
from webapp.models import Product, OrderProduct, Order, ORDER_STATUS_CHOICES
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.contrib import messages
from webapp.mixins import StatsMixin


class IndexView(StatsMixin, ListView):
    model = Product
    template_name = 'index.html'

    def get_queryset(self):
        return Product.objects.filter(in_order=True)


class ProductView(StatsMixin, DetailView):
    model = Product
    template_name = 'product/detail.html'


class ProductCreateView(PermissionRequiredMixin, StatsMixin, CreateView):
    model = Product
    template_name = 'product/create.html'
    fields = ('name', 'category', 'price', 'photo', 'in_order')
    permission_required = 'webapp.add_product', 'webapp.can_have_piece_of_pizza'
    permission_denied_message = '403 Доступ запрещён!'

    def get_success_url(self):
        return reverse('webapp:product_detail', kwargs={'pk': self.object.pk})


class ProductUpdateView(LoginRequiredMixin, StatsMixin, UpdateView):
    model = Product
    template_name = 'product/update.html'
    fields = ('name', 'category', 'price', 'photo', 'in_order')
    context_object_name = 'product'

    def get_success_url(self):
        return reverse('webapp:product_detail', kwargs={'pk': self.object.pk})


class ProductDeleteView(LoginRequiredMixin, StatsMixin, DeleteView):
    model = Product
    template_name = 'product/delete.html'
    success_url = reverse_lazy('webapp:index')
    context_object_name = 'product'

    def delete(self, request, *args, **kwargs):
        product = self.object = self.get_object()
        product.in_order = False
        product.save()
        return HttpResponseRedirect(self.get_success_url())


class BasketChangeView(StatsMixin, View):
    def get(self, request, *args, **kwargs):
        products = request.session.get('products', [])

        pk = request.GET.get('pk')
        action = request.GET.get('action')
        next_url = request.GET.get('next', reverse('webapp:index'))

        if action == 'add':
            product = get_object_or_404(Product, pk=pk)
            if product.in_order:
                products.append(pk)
        else:
            for product_pk in products:
                if product_pk == pk:
                    products.remove(product_pk)
                    break

        request.session['products'] = products
        request.session['products_count'] = len(products)

        return redirect(next_url)


class BasketView(StatsMixin, CreateView):
    model = Order
    form_class = BasketOrderCreateForm
    template_name = 'product/basket.html'
    success_url = reverse_lazy('webapp:index')

    def get_context_data(self, **kwargs):
        basket, basket_total = self._prepare_basket()
        kwargs['basket'] = basket
        kwargs['basket_total'] = basket_total
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        if self._basket_empty():
            form.add_error(None, 'В корзине отсутствуют товары!')
            return self.form_invalid(form)
        response = super().form_valid(form)
        self._save_order_products()
        self._clean_basket()
        messages.success(self.request, 'Заказ оформлен!')
        return response

    def _prepare_basket(self):
        totals = self._get_totals()
        basket = []
        basket_total = 0
        for pk, qty in totals.items():
            product = Product.objects.get(pk=int(pk))
            total = product.price * qty
            basket_total += total
            basket.append({'product': product, 'qty': qty, 'total': total})
        return basket, basket_total

    def _get_totals(self):
        products = self.request.session.get('products', [])
        totals = {}
        for product_pk in products:
            if product_pk not in totals:
                totals[product_pk] = 0
            totals[product_pk] += 1
        return totals

    def _basket_empty(self):
        products = self.request.session.get('products', [])
        return len(products) == 0

    def _save_order_products(self):
        totals = self._get_totals()
        for pk, qty in totals.items():
            OrderProduct.objects.create(product_id=pk, order=self.object, amount=qty)

    def _clean_basket(self):
        if 'products' in self.request.session:
            self.request.session.pop('products')
        if 'products_count' in self.request.session:
            self.request.session.pop('products_count')


class OrderListView(ListView):
    template_name = 'order/list.html'
    context_object_name = 'orders'

    def get_queryset(self):
        if self.request.user.has_perm('webapp:view_order'):
            return Order.objects.all().order_by('-created_at')
        return self.request.user.orders.all().order_by('-created_at')


class OrderDetailView(DetailView):
    template_name = 'order/detail.html'

    def get_queryset(self):
        if self.request.user.has_perm('webapp:view_order'):
            return Order.objects.all()
        return self.request.user.orders.all()


class OrderCreateView(CreateView):
    model = Order
    template_name = 'order/create.html'
    form_class = ManualOrderForm


class OrderUpdateView(UpdateView):
    model = Order
    context_object_name = 'order'
    form_class = ManualOrderForm
    template_name = 'order/update.html'


class OrderDeliverView(View):
    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get("pk")
        order = Order.objects.get(pk=pk)
        context = {
            'order': order
        }
        return render(request, 'order/deliver.html', context)

    def post(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        order = Order.objects.get(pk=pk)
        order.status = ORDER_STATUS_CHOICES[3][0]
        order.save()
        return redirect('webapp:order_detail', self.kwargs.get('pk'))


class OrderCancelView(View):
    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        order = Order.objects.get(pk=pk)
        return render(request, 'order/cancel.html', context={'order': order})

    def post(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        order = Order.objects.get(pk=pk)
        order.status = ORDER_STATUS_CHOICES[4][0]
        order.save()
        return redirect('webapp:order_detail', self.kwargs.get('pk'))


class OrderProductCreateView(CreateView):
    model = OrderProduct
    template_name = 'order/create_orderproduct.html'
    form_class = OrderProductForm

    def form_valid(self, form):
        pk = self.kwargs.get('pk')
        order = Order.objects.get(pk=pk)
        print("order", order)
        OrderProduct.objects.create(
            order=order,
            product=form.cleaned_data['product'],
            amount=form.cleaned_data['amount']
        )
        return redirect('webapp:order_detail', self.kwargs.get('pk'))


class OrderProductUpdateView(UpdateView):
    model = OrderProduct
    template_name = 'order/update_orderproduct.html'
    form_class = OrderProductForm

    def form_valid(self, form):
        self.object = form.save()
        return redirect('webapp:order_detail', self.kwargs.get('pk'))


class OrderProductDeleteView(DeleteView):
    model = OrderProduct
    context_object_name = 'product'
    template_name = 'order/delete_orderproduct.html'
    form_class = OrderProductForm

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return redirect('webapp:order_detail', self.kwargs.get('pk'))
