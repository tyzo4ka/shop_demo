from datetime import datetime, timedelta
from audioop import reverse
from django.urls import reverse_lazy
from webapp.models import Product, OrderProduct, Order
from django.shortcuts import reverse, redirect, render
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, TemplateView


class StatisticMixin:

    def dispatch(self, request, *args, **kwargs):
        timenow = datetime.now()
        timenow_str = timenow.__str__()

        if request.session.get("timenow") == None:
            request.session['timenow'] = timenow_str
        else:
            previous_time = request.session.get("timenow")
            last_time = datetime.strptime(previous_time, "%Y-%m-%d %H:%M:%S.%f")
            new_time = timenow
            request.session['timenow'] = new_time.__str__()
            difference = new_time - last_time
            difference_str = difference.__str__()
            if request.session.get("all_time") == None:
                request.session['all_time'] = difference_str
            else:
                all_time = request.session.get("all_time")
                all_time2 = datetime.strptime(all_time, "%Y-%m-%d %H:%M:%S.%f")
                all_time = all_time2 + difference
                request.session["all_time"] = all_time.__str__()
            if 'counter' in request.session:
                request.session['counter'] += 1
            else:
                request.session['counter'] = 0
            if 'pages' in request.session:
                if request.path in request.session["pages"]:
                    request.session[request.path]['qt'] += 1
                    if request.session[request.path].get("pagetime") is None:
                        request.session[request.path]["pagetime"] = difference_str
                    else:
                        old_pagetime = request.session[request.path].get('pagetime')
                        old_pagetime_data = datetime.strptime(old_pagetime, "%Y-%m-%d %H:%M:%S.%f")
                        new_data = old_pagetime_data + timedelta(seconds=difference.total_seconds())
                        request.session[request.path]['pagetime'] = new_data.__str__()
                else:
                    request.session['pages'].append(request.path)
                    request.session[request.path] = {"qt": 0}

            else:
                request.session['pages'] = []
        return super().dispatch(request, *args, **kwargs)


class IndexView(StatisticMixin, ListView):
    model = Product
    template_name = 'index.html'


class ProductView(DetailView):
    model = Product
    template_name = 'product/detail.html'


class ProductCreateView(CreateView):
    model = Product
    template_name = 'product/create.html'
    fields = ('name', 'category', 'price', 'photo')
    success_url = reverse_lazy('webapp:index')


class BasketChangeView(View):
    def get(self, request, *args, **kwargs):
        products = request.session.get('products', [])

        pk = request.GET.get('pk')
        action = request.GET.get('action')
        next_url = request.GET.get('next', reverse('webapp:index'))

        if action == 'add':
            products.append(pk)
        else:
            for product_pk in products:
                if product_pk == pk:
                    products.remove(product_pk)
                    break

        request.session['products'] = products
        request.session['products_count'] = len(products)

        return redirect(next_url)


class BasketView(CreateView):
    model = Order
    fields = ('first_name', 'last_name', 'phone', 'email')
    template_name = 'product/basket.html'
    success_url = reverse_lazy('webapp:index')

    def get_context_data(self, **kwargs):
        basket, basket_total = self._prepare_basket()
        kwargs['basket'] = basket
        kwargs['basket_total'] = basket_total
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        if self._basket_empty():
            form.add_error(None, 'В корзине отсутствуют товары!')
            return self.form_invalid(form)
        response = super().form_valid(form)
        self._save_order_products()
        self._clean_basket()
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


class StatisticView(StatisticMixin, View):
    def get(self, request, *args, **kwargs):
        all_time = request.session.get("all_time")
        counter = request.session.get("counter")
        pages = set(request.session.get("pages"))
        print("pages", pages)
        pages_statistic = {}

        for path in pages:
            pages_statistic[path] = {}
            print('request.session.get(path).get("pagetime")', request.session[path].get("pagetime"))
            pages_statistic[path]["pagetime"] = request.session[path].get("pagetime")
            pages_statistic[path]["qt"] = request.session.get(path).get("qt")

        print('pages_statistic', pages_statistic)
        return render(request, 'product/statistic.html', {'all_time': all_time,
                                                          "counter": counter,
                                                          "pages": pages,
                                                          "pages_statistic": pages_statistic})
