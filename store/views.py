from decimal import Decimal
from django.db import transaction
from django.shortcuts import render,get_object_or_404,redirect
from store.models import Category,Product,Cart,CartItem,Order,OrderItem
from store.forms import SignUpForm
from django.contrib.auth.models import Group,User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login , authenticate,logout
from django.core.paginator import Paginator,EmptyPage,InvalidPage
from django.contrib.auth.decorators import login_required





# Create your views here.
def index(request,category_slug=None):
    products=None
    category_page=None
    if category_slug!=None:
        category_page=get_object_or_404(Category,slug=category_slug)
        products=Product.objects.all().filter(category=category_page,available=True)
    else :
        products=Product.objects.all().filter(available=True)
    
    #12 / 3 = 4
    paginator=Paginator(products,3)
    try:
        page=int(request.GET.get('page','1'))
    except:
        page=1

    try:
        productperPage=paginator.page(page)
    except (EmptyPage,InvalidPage):
        productperPage=paginator.page(paginator.num_pages)
    
    return render(request,'index.html',{'products':productperPage,'category':category_page})

def productPage(request,category_slug,product_slug):
    try:
        product=Product.objects.get(category__slug=category_slug,slug=product_slug)
    except Exception as e :
          raise e
    return render(request,'product.html',{'product':product})

def _cart_id(request):
    cart=request.session.session_key
    if not cart:
        cart=request.session.create()
    return cart

@login_required(login_url='signIn')
def addCart(request,product_id):
        #ดึงสินค้าที่เราซื้อมาใช้งาน
        product=Product.objects.get(id=product_id)
        #สร้างตะกร้าสินค้า
        try:
            cart=Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart=Cart.objects.create(cart_id=_cart_id(request))
            cart.save()
        
        try:
            #ซื้อรายการสินค้าซ้ำ
            cart_item=CartItem.objects.get(product=product,cart=cart)
            if cart_item.quantity<cart_item.product.stock :
                #เปลี่ยนจำนวนรายการสินค้า
                cart_item.quantity+=1
                #บันทึก/อัพเดทค่า
                cart_item.save()
        except CartItem.DoesNotExist:
            #ซื้อรายการสินค้าครั้งแรก
            #บันทึกลงฐานข้อมูล
            cart_item=CartItem.objects.create(
                product=product,
                cart=cart,
                quantity=1
            )
            cart_item.save()
        return redirect(request.META.get('HTTP_REFERER', '/'))
    
def calculate_shipping_fee(postcode):
    try:
        postcode = int(postcode)
        if 10000 <= postcode <= 10999:
            return Decimal('30.00')  # กทม
        elif 11000 <= postcode <= 11999:
            return Decimal('50.00')  # ปริมณฑล
        else:
            return Decimal('70.00')  # ต่างจังหวัด
    except:
        return Decimal('70.00')  # Default ถ้าไม่มีหรือไม่ถูกต้อง

def cartdetail(request):
    total = Decimal('0.00')
    shipping_fee = Decimal('0.00')  # 👉 กำหนดไว้ก่อน
    grand_total = Decimal('0.00')   # 👉 รวม total + shipping_fee
    counter = 0
    cart_items = None
  

    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_items = CartItem.objects.filter(cart=cart, active=True)

        for item in cart_items:
            total += item.product.price * item.quantity
            counter += item.quantity
    except Exception as e:
        pass

    if request.method == "POST":
        # รับข้อมูลจากแบบฟอร์ม
        name = request.POST.get('name')
        address = request.POST.get('address')
        city = request.POST.get('city')
        postcode = request.POST.get('postcode')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        payment_slip = request.FILES.get('payment_slip')
        shipping_fee = calculate_shipping_fee(postcode)
        grand_total  = total + shipping_fee

        with transaction.atomic():
            order = Order.objects.create(
                name=name,
                address=address,
                city=city,
                postcode=postcode,
                total=grand_total,
                email=email,
                phone=phone,
                payment_slip=payment_slip,  # บันทึกไฟล์ลง model
                is_paid=False,  # ยังไม่อนุมัติ
                shipping_fee=shipping_fee
            )

        # บันทึกรายการสั่งซื้อ + ลด stock + ลบตะกร้า
        for item in cart_items:
            OrderItem.objects.create(
                product=item.product.name,
                quantity=item.quantity,
                price=item.product.price,
                order=order
            )

            product = Product.objects.get(id=item.product.id)
            product.stock = product.stock - item.quantity
            product.save()
            item.delete()

        return redirect('thankyou')
    
    
    return render(request, 'cartdetail.html', {
        'cart_items': cart_items,
        'total': total,
        'shipping_fee': shipping_fee,
        'grand_total': grand_total,
        'counter': counter,
    })

   

def removeCart(request,product_id):
    #ทำงานกับตะกร้าสินค้า A
    cart=Cart.objects.get(cart_id=_cart_id(request))
    #ทำงานกับสินค้าที่จะลบ 1
    product=get_object_or_404(Product,id=product_id)
    cartItem=CartItem.objects.get(product=product,cart=cart)
    #ลบรายการสินค้า 1 ออกจากตะกร้า A โดยลบจาก รายการสินค้าในตะกร้า (CartItem)
    cartItem.delete()
    return redirect('cartdetail')

def signUpView(request):
    if request.method=='POST':
        form=SignUpForm(request.POST)
        if form.is_valid():
            #บันทึกข้อมูล User
            form.save()
            #บันทึก Group Customer
            #ดึง username จากแบบฟอร์มมาใช้
            username=form.cleaned_data.get('username')
            #ดึงข้อมูล user จากฐานข้อมูล
            signUpUser=User.objects.get(username=username)
            #จัด Group
            customer_group=Group.objects.get(name="Customer")
            customer_group.user_set.add(signUpUser)
            return redirect('/register/success/') 
    else :
        form=SignUpForm()
    return render(request,"signup.html",{'form':form})

def signInView(request):
    if request.method=='POST':
        form=AuthenticationForm(data=request.POST)
        if form.is_valid():
            username=request.POST['username']
            password=request.POST['password']
            user=authenticate(username=username,password=password)
            if user is not None :
                login(request,user)
                return redirect('home')
            else :
                return redirect('signUp')
    else:
        form=AuthenticationForm()
    return render(request,'signin.html',{'form':form})

def signOutView(request):
    logout(request)
    return redirect('signIn')

def search(request):
    products=Product.objects.filter(name__contains=request.GET['title'])
    return render(request,'index.html',{'products':products})


def orderHistory(request):
    if request.user.is_authenticated:
        email=str(request.user.email)
        orders=Order.objects.filter(email=email)
    return render(request,'orders.html',{'orders':orders})

def viewOrder(request,order_id):
    if request.user.is_authenticated:
        email=str(request.user.email)
        order=Order.objects.get(email=email,id=order_id)
        orderitem=OrderItem.objects.filter(order=order)
        return render(request,'viewOrder.html',{'order': order, 'order_items': orderitem})
    else:
     return redirect('login') 

def thankyou(request):
    return render(request,'thankyou.html')

def register_success(request):
    return render(request, 'register_success.html')


