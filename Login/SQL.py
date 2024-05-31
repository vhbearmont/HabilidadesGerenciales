#import pyodbc
from flask import Flask, render_template, request, redirect, url_for, send_file, g, session, json
import requests
import json
import difflib
from weasyprint import HTML
from io import BytesIO
from num2words import num2words
import uuid
import qrcode
import cx_Oracle
from datetime import datetime

conn = None
connection = None
cursor = None
grupo = None
autenticaded = False
empleado = False
username = ''
password = ''
dsn = '192.168.100.43:1521/XE'
#dsn = '10.254.255.114:1521/XE'
connection = None

def get_db():
    if 'connection' not in g:
        username = session.get('username')
        password = session.get('password')
        print("USERNAME: ", username)
        print("PASSWORD: ", password)
        if username is None or password is None:
           return redirect(url_for('login'))
        g.connection = cx_Oracle.connect(username, password, dsn)
        g.cursor = g.connection.cursor()
    return g.connection, g.cursor

app = Flask(__name__)
app.secret_key = 'secreto'

@app.route("/login", methods=['GET', 'POST'])
def index():
    global autenticaded
    user = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
           connection = cx_Oracle.connect(username, password, dsn)
           session['username'] = username
           session['password'] = password
           connection.close()
        except cx_Oracle.DatabaseError:
           return render_template('login.html')
        connection, cursor = get_db()
        cursor.execute("SELECT role FROM session_roles")
        roles = cursor.fetchall()
        print(roles[0][0])
        if roles[0][0] == "ADMINISTRADOR":
           cursor.execute('alter session set "_ORACLE_SCRIPT"=TRUE')
           autenticaded = True
           return redirect(url_for('admin'))
        elif roles[0][0] == "AUDITOR":
           autenticaded = True
           return redirect(url_for('auditor'))
        elif roles[0][0] == "EMPLEADO":
           autenticaded = True
           empleado = True
           return redirect(url_for('empleado'))
        elif roles[0][0] == "CLIENTE":
           autenticaded = True
           empleado = False
           return redirect(url_for('cliente'))
    else:
        return render_template('login.html')

@app.route("/admin", methods=['GET', 'POST'])
def admin():
    global usuarios
    if autenticaded:
        connection, cursor = get_db()
        username = request.args.get('username')  # Obtenemos el username de la URL
        cursor.execute("SELECT id, nombre_completo, email, tipo_de_usuario, nombre_de_usuario FROM system.usuarios")
        rows = cursor.fetchall()
        #print(rows)
        data_list = []
        for row in rows:
          data_dict = {'id': row[0], 'nombre': row[1], 'email': row[2], 'rol': row[3], 'username': row[4]}
          data_list.append(data_dict)
        print('Data list admin: ', data_list)
        lista_movimientos = []
        cursor.execute("SELECT fecha, descripcion FROM system.movimientos")
        rows = cursor.fetchall()
        for row in rows:
          dict_movimientos = {'fecha': row[0], 'descripcion': row[1]}
          lista_movimientos.append(dict_movimientos)
        return render_template('admin.html', usuarios=data_list, movimientos=lista_movimientos)
    return redirect(url_for("index"))

@app.route("/auditor", methods=['POST', 'GET'])
def auditor():
    global autenticaded
    print("autenticado: ", autenticaded) 
    if autenticaded:
        connection, cursor = get_db()
        if(request.method == 'POST'):
           nombre = request.form['nombre']
           cantidad = request.form['cantidad']
           precio = request.form['precio']
           id = request.form['id']
           print(f"UPDATE SYSTEM.PRODUCTOS SET nombre = '{nombre}', cantidad = {cantidad}, precio = {precio} WHERE ID = {id}")
           try:
             cursor.execute(f"UPDATE SYSTEM.PRODUCTOS SET nombre = '{nombre}', cantidad = {cantidad}, precio = {precio} WHERE ID = {id}")
             connection.commit()
           except cx_Oracle.DatabaseError as e:
             print("Error al procesar el cambio", e)
        cursor.execute("SELECT ID, NOMBRE, CANTIDAD, PRECIO FROM SYSTEM.PRODUCTOS")
        rows = cursor.fetchall()
        data_list = []
        for row in rows:
          dict_productos = {"id": row[0], "nombre": row[1], "cantidad": row[2], "precio": row[3]}
          data_list.append(dict_productos)
        return render_template('auditor.html', articulos=data_list)
    return redirect(url_for("index"))

@app.route("/empleado")
def empleado():
    se_filtra = request.args.get('se_filtra')
    connection, cursor = get_db()
    cursor.execute("SELECT ID, NOMBRE, PRECIO, CANTIDAD FROM SYSTEM.PRODUCTOS")
    rows = cursor.fetchall()
    products_list = []
    for row in rows:
      dict_productos = {"id": row[0], "nombre": row[1], "precio": row[2], "cantidad": row[3]}
      products_list.append(dict_productos)
    cursor.execute("SELECT USER FROM DUAL")
    user = cursor.fetchone()[0]
    cursor.execute(f"SELECT ID FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    #print(f"SELECT ID FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    user_id = cursor.fetchone()[0]
    print(user_id)
    cursor.execute(f"SELECT ID FROM SYSTEM.EMPLEADOS WHERE ID_USUARIO = {user_id}")
    empleado_id = cursor.fetchone()[0]
    cursor.execute(f"SELECT * FROM SYSTEM.EMPLEADOS WHERE ID = {empleado_id}")
    empleado_rows = cursor.fetchall()
    empleado_list = []
    for row in empleado_rows:
      dict_empleados = {"id": row[0], "rol": row[2], "sueldo_diario": row[3]}
      empleado_list.append(dict_empleados)
    #print("empleado_list: ", empleado_list)
    cursor.execute(f"SELECT RFC, NOMBRE_COMPLETO FROM SYSTEM.USUARIOS WHERE ID = {user_id}")
    #print(f"SELECT RFC, NOMBRE_COMPLETO FROM SYSTEM.USUARIOS WHERE ID = {user_id}")
    usuario_rows = cursor.fetchall()
    usuario_list = []
    for row in usuario_rows:
      #print("row usuario_list: ", row)
      dict_usuario = {"rfc": row[0], "nombre": row[1]}
      usuario_list.append(dict_usuario)
    #print("Usuario_list: ", usuario_list)
    sueldo_diario = empleado_list[0]["sueldo_diario"]
    cursor.execute(f"SELECT * FROM SYSTEM.NOMINAS WHERE ID_EMPLEADO = {empleado_id}")
    nominas_rows = cursor.fetchall()
    nomina_list = []
    for row in nominas_rows:
      raw_uuid = row[7]
      hex_uuid = raw_uuid.hex()
      uuid_obj = uuid.UUID(hex_uuid)
      dict_nominas = {"id": row[1], "fecha": row[2], "sueldo_base": row[3], "faltas": row[4], "descuentos": row[5], "adicionales": row[6], "uuid": uuid_obj, "total": row[8], "rfc": usuario_list[0]["rfc"], "nombre": usuario_list[0]["nombre"], "rol": empleado_list[0]["rol"], "sueldo_diario": sueldo_diario}
      nomina_list.append(dict_nominas)
    cursor.execute("SELECT SUM(CANTIDAD) FROM SYSTEM.CARRITO_DE_COMPRAS WHERE ID_CLIENTE = :id_cliente", id_cliente = user_id)
    resultado = cursor.fetchone()
    carrito= resultado[0] if resultado[0] is not None else 0
    #print(nomina_list[0])
    cliente_dict = {}
    if(se_filtra=='1'):
      print("entre al if de se filtra")
      json_data = request.args.get('articulos')
      products_list = json.loads(json_data)
      print("imprimiendo lista filtrada: ", products_list)

    return render_template('empleado.html', nominas=nomina_list, carrito=carrito, articulos=products_list, usuario=cliente_dict)


@app.route("/nomina_generada", methods=['POST', 'GET'])
def nomina_generada():
    fecha = request.form["fecha"]
    rfc = request.form["rfc"]
    nombre = request.form["nombre"]
    idEmpleado = request.form["id"]
    sueldo_base = float(request.form["sueldo_base"])
    sueldo_diario = float(request.form["sueldo_diario"])
    direccion = request.form["direccion"]
    razon_social = request.form["razon_social"]
    faltas = request.form["faltas"]
    descuentos = float(request.form["descuentos"])
    adicionales = float(request.form["adicionales"])
    clave_uuid = request.form["uuid"]
    total = adicionales - descuentos + sueldo_base
    pago_letra = num2words(total, lang='es')

    html = render_template('nomina_generada.html', fecha=fecha, rfc=rfc, nombre=nombre, idEmpleado=idEmpleado, sueldo_base=sueldo_base, sueldo_diario=sueldo_diario, direccion=direccion, razon_social=razon_social, faltas=faltas, descuentos=descuentos, adicionales=adicionales, total=total, pago_letra=pago_letra, uuid=clave_uuid)
    PDF = HTML(string=html).write_pdf()

    response=send_file(BytesIO(PDF), as_attachment=True, download_name='nomina.pdf')
    response.headers["Refresh"] = '5; URL=' + url_for('empleado') 
    return response

#return send_file('nomina_generada.html', fecha=fecha, rfc=rfc, curp=curp, nombre=nombre, idEmpleado=idEmpleado, puesto=puesto, sueldo_base=sueldo_base, sueldo_diario=sueldo_diario, direccion=direccion, razon_social=razon_social, faltas=faltas, descuentos=descuentos, adicionales=adicionales, total=total, seguro_social=seguro_social)

@app.route("/buscar_articulo_cliente", methods=['POST'])
def buscar_articulo_cliente():
    connection, cursor = get_db()
    cursor.execute("SELECT ID, NOMBRE, PRECIO, CANTIDAD FROM SYSTEM.PRODUCTOS")
    rows = cursor.fetchall()
    articulos = []
    for row in rows:
      dict_productos = {"id": row[0], "nombre": row[1], "precio": row[2], "cantidad": row[3]}
      articulos.append(dict_productos)
    articulosFiltrados = []
    string = request.form['entrada']
    nombres_medicamentos = [art["nombre"] for art in articulos]
    print(nombres_medicamentos)
    matches = difflib.get_close_matches(string, nombres_medicamentos, n=1, cutoff=0.3) 
    print(matches)
    for art in articulos:
        if art["nombre"] in matches:
            articulosFiltrados.append(art)
    if(string == ''):
     articulosFiltrados = articulos
    json_data = json.dumps(articulosFiltrados)
    return redirect(url_for('cliente', articulos=json_data,se_filtra=1))

@app.route("/buscar_articulo_empleado", methods=['POST'])
def buscar_articulo_empleado():
    connection, cursor = get_db()
    cursor.execute("SELECT ID, NOMBRE, PRECIO, CANTIDAD FROM SYSTEM.PRODUCTOS")
    rows = cursor.fetchall()
    articulos = []
    for row in rows:
      dict_productos = {"id": row[0], "nombre": row[1], "precio": row[2], "cantidad": row[3]}
      articulos.append(dict_productos)
    articulosFiltrados = []
    string = request.form['entrada']
    nombres_medicamentos = [art["nombre"] for art in articulos]
    print(nombres_medicamentos)
    matches = difflib.get_close_matches(string, nombres_medicamentos, n=1, cutoff=0.3) 
    print(matches)
    for art in articulos:
        if art["nombre"] in matches:
            articulosFiltrados.append(art)
    if(string == ''):
     articulosFiltrados = articulos

    json_data = json.dumps(articulosFiltrados)
    return redirect(url_for('empleado', articulos=json_data,se_filtra=1))

@app.route("/cliente", methods=['POST', 'GET'])
def cliente():
    se_filtra = request.args.get('se_filtra')
    print("valor de se_filtra: ", se_filtra)
    connection, cursor= get_db()
    cursor.execute("SELECT ID, NOMBRE, PRECIO, CANTIDAD FROM SYSTEM.PRODUCTOS")
    rows = cursor.fetchall()
    products_list = []
    for row in rows:
      dict_productos = {"id": row[0], "nombre": row[1], "precio": row[2], "cantidad": row[3]}
      products_list.append(dict_productos)
    #print("products_list: ", products_list)
    cursor.execute("SELECT USER FROM DUAL")
    user = cursor.fetchone()[0].upper()
    #print("usuario de cliente: ", user)
    cursor.execute(f"SELECT ID FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    id_user = cursor.fetchone()[0]
    print("id_user del cliente: ", id_user)
    cursor.execute(f"SELECT ID FROM SYSTEM.CLIENTES WHERE ID_USUARIO = {id_user}")
    cliente_id = cursor.fetchone()[0]
    cursor.execute("""SELECT system.facturas.id, system.facturas.fecha,
                      system.productos.id, system.productos.nombre, system.detalles_factura.precio, system.detalles_factura.cantidad
                      FROM system.facturas
                      JOIN system.detalles_factura ON system.facturas.id = system.detalles_factura.id_factura
                      JOIN system.productos ON system.detalles_factura.id_producto = system.productos.id
                      WHERE system.facturas.id_cliente = :cliente_id
                      ORDER BY system.facturas.id""", cliente_id=cliente_id)
    rows_articulos = cursor.fetchall()
    articulos = []
    for row in rows_articulos:
      dict_articulos = {"id": row[2], "nombre": row[3], "precio": row[4], "cantidad": row[5], "total": row[5] * row[4]}
      articulos.append(dict_articulos)
    #print("articulos", articulos)
    cursor.execute("""SELECT system.usuarios.rfc, system.usuarios.nombre_completo, system.usuarios.cp, system.usuarios.email,
       system.facturas.id, system.facturas.fecha, system.facturas.uuid,
       system.clientes.regimen_fiscal, system.clientes.uso_fiscal, system.facturas.total
       FROM system.usuarios
       JOIN system.clientes ON system.usuarios.ID = system.clientes.ID_usuario
       JOIN system.facturas ON system.clientes.ID = system.facturas.ID_cliente
       WHERE system.usuarios.ID = :user_id
       ORDER BY SYSTEM.FACTURAS.ID""", user_id=id_user)
    datos_fac = cursor.fetchall()
    facturas = []
    cliente_send = {}
    for dato in datos_fac:
      hex_uuid = dato[6].hex()
      uuid_obj = uuid.UUID(hex_uuid)
      factura_dic = {"rfc": dato[0], "nombre": dato[1], "cp": dato[2], "email": dato[3], "id": dato[4], "fecha": dato[5], "uuid": uuid_obj, "regimen_fiscal": dato[7], "uso_fiscal": dato[8], "total": dato[9]}
      facturas.append(factura_dic)
    cursor.execute("""SELECT system.usuarios.rfc, system.usuarios.nombre_completo, system.usuarios.cp, system.usuarios.email,
                      system.clientes.regimen_fiscal, system.clientes.uso_fiscal
                      FROM system.usuarios
                      JOIN system.clientes ON system.usuarios.ID = system.clientes.ID_usuario
                      WHERE system.usuarios.ID = :id_usuario """, id_usuario=id_user)
    dato_send = cursor.fetchone()
    cliente_send = { "rfc": dato_send[0], "nombre": dato_send[1], "cp": dato_send[2], "email": dato_send[3], "regimen_fiscal": dato_send[4], "uso_fiscal": dato_send[5]}
    cursor.execute("SELECT SUM(CANTIDAD) FROM SYSTEM.CARRITO_DE_COMPRAS WHERE ID_CLIENTE = :id_cliente", id_cliente = id_user)
    resultado = cursor.fetchone()
    carrito= resultado[0] if resultado[0] is not None else 0
    if(se_filtra=='1'):
      print("entre al if de se filtra")
      json_data = request.args.get('articulos')
      products_list = json.loads(json_data)
      print("imprimiendo lista filtrada: ", products_list)
    print("cliente send en cliente: ", cliente_send)

    return render_template('cliente.html', carrito=carrito, articulos=products_list, facturas=facturas, usuario=cliente_send)

@app.route("/eliminar_usuario", methods=['POST'])
def eliminar_usuario():
    global usuarios
    connection, cursor = get_db()
    cursor.execute('alter session set "_ORACLE_SCRIPT"=TRUE')
    id = request.form["id"]
    username = request.form["username"]
    cursor.execute(f"DELETE FROM SYSTEM.USUARIOS WHERE ID = {id}")
    cursor.execute(f"DROP USER {username}")
    connection.commit()
    return redirect(url_for("admin"))

@app.route("/agregar_usuario", methods=['POST'])
def agregar_usuario():
    global usuarios, users
    connection, cursor = get_db()
    cursor.execute('alter session set "_ORACLE_SCRIPT"=TRUE')
    usuario = request.form["username"]
    password = request.form["password"]
    email = request.form["email"]
    rol = request.form["role"]
    nombre = request.form["nombre"]
    regimen_fiscal = request.form["regimenFiscal"]
    uso_fiscal = request.form["usoFiscal"]
    area = request.form["area"]
    salario = request.form["salario"]
    fecha_nac = request.form["fechaNacimiento"]
    domicilio = request.form["domicilio"]
    cp = request.form["cp"]
    telefono = request.form["telefono"]
    sexo = request.form["sexo"]
    rfc = request.form["rfc"]
    id_usuario = cursor.var(cx_Oracle.NUMBER)
    print(usuario)
    print(password)
    #user = request.form["user"]
    #userDict = eval(user)
    try:
       cursor.execute("""
                      INSERT INTO system.usuarios (ID, Nombre_de_usuario, Contraseña, Tipo_de_usuario, RFC, Nombre_completo, Fecha_de_nacimiento, Sexo, Domicilio, CP, Email, Telefono)
                      VALUES (system.usuarios_seq.NEXTVAL, :nombre_usuario, :contraseña, :tipo, :rfc, :nombre, TO_DATE(:fecha_nac, 'YYYY-MM-DD'), :sexo, :domicilio, :cp, :email, :telefono)
                      RETURNING ID INTO :id_usuario
                      """, {'nombre_usuario':usuario.upper(), 'contraseña':password, 'tipo':rol, 'rfc':rfc, 'nombre':nombre, 'fecha_nac':fecha_nac,  'sexo':sexo, 'domicilio':domicilio, 'cp':cp, 'email':email, 'telefono':telefono, 'id_usuario':id_usuario})
       print("id del usuario nuevo: ", id_usuario.getvalue()[0])
       if(rol == "cliente"):
         cursor.execute("""
                        INSERT INTO system.clientes (ID, ID_Usuario, Regimen_fiscal, Uso_Fiscal)
                        VALUES (system.clientes_seq.NEXTVAL, :IDUsuario, :regimen_fiscal, :uso_fiscal)
                        """, IDUsuario=id_usuario.getvalue()[0], regimen_fiscal=regimen_fiscal, uso_fiscal=uso_fiscal)
       elif(rol == "empleado"):
         cursor.execute("""
                        INSERT INTO system.empleados (ID, ID_Usuario, Area, Salario)
                        VALUES (system.empleados_seq.NEXTVAL, :IDUsuario, :area, :salario)
                        """, IDUsuario=id_usuario.getvalue()[0], area=area, salario=salario)
    #userDict["usuarios"].append(nuevo_usuario)
    #cursor.execute("SELECT id, nombre_completo, email, tipo_de_usuario FROM system.usuarios")
    #cursor.execute("SELECT * from system.clientes")
       #print(f"CREATE USER {usuario} IDENTIFIED BY {password}")
       cursor.execute(f"CREATE USER {usuario} IDENTIFIED BY {password}")
       cursor.execute(f"GRANT {rol} TO {usuario}")
       connection.commit()
    except cx_Oracle.IntegrityError as e:
       connection.rollback()
    return redirect(url_for("admin"))

@app.route("/registrar_usuario", methods=['POST', 'GET'])
def registro():
    user = request.form["user"]
    print("holaaaaaa", user)
    #userDict = eval(user)
    return render_template('registrar_usuario.html', user=user)

@app.route("/agregar_movimiento", methods=['POST'])
def agregar_movimient():
    connection, cursor = get_db()
    fecha = request.form["date"]
    descripcion = request.form["description"]
    try:
       cursor.execute("""INSERT INTO SYSTEM.MOVIMIENTOS (id, fecha, descripcion)
                      VALUES (system.movimientos_seq.NEXTVAL, TO_DATE(:fecha, 'YYYY-MM-DD'), :descripcion)
                      """, fecha=fecha, descripcion=descripcion)
       connection.commit()
    except cx_Oracle.IntegrityError as e:
       connection.rollback()
    return redirect(url_for("admin"))

@app.route("/registrar_movimiento")
def registrar_movimiento():
    return render_template('registrar_movimiento.html')

@app.route("/modificar_articulo", methods=['POST'])
def modificar_articulo():
    if request.method == 'POST':
        nombre = request.form['nombre']
        cantidad = int(request.form['cantidad'])
        precio = float(request.form['precio'])
        id = request.form['id']
    return render_template('modificar_articulo.html', nombre=nombre, cantidad=cantidad, precio=precio, id=id)

@app.route("/logout", methods=['GET', 'POST'])
def logout():
    # Aquí puedes agregar lógica para cerrar la sesión del usuario
    # Por ahora, simplemente redireccionaremos al usuario a la página de inicio de sesión
    if request.method == 'POST':
        # Puedes agregar aquí lógica adicional para manejar la solicitud POST de cierre de sesión si es necesario
        pass
    return redirect(url_for('index'))

@app.route("/agregar_al_carrito_empleado", methods=['POST'])
def agregar_a_carrito_empleado():
    global lista_compras
    connection, cursor = get_db()
    cursor.execute("SELECT USER FROM DUAL")
    user = cursor.fetchone()[0]
    cursor.execute(f"SELECT ID FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    id_empleado = cursor.fetchone()[0]
    if request.method == 'POST':
        id = request.form['id']
        cursor.execute("SELECT cantidad FROM SYSTEM.CARRITO_DE_COMPRAS WHERE id_producto = :id AND id_cliente = :id_empleado", id=id, id_empleado = id_empleado)
        resultado = cursor.fetchone()
        if resultado:
         try:
          nueva_cantidad = resultado[0] + 1
          cursor.execute("UPDATE SYSTEM.CARRITO_DE_COMPRAS SET cantidad = :nueva_cantidad WHERE id_producto = :id AND id_cliente = :id_empleado", nueva_cantidad = nueva_cantidad, id=id, id_empleado=id_empleado)
          connection.commit()
         except cx_Oracle.DatabaseError as e:
          print(e)
        else:
         try:
          cursor.execute("""Insert INTO SYSTEM.CARRITO_DE_COMPRAS (id, id_cliente, id_producto, cantidad)
                          VALUES (system.carrito_seq.NEXTVAL, :id_empleado, :id, 1)
                         """, id_empleado=id_empleado, id=id)
          connection.commit()
         except cx_Oracle.DatabaseError as e:
          print("no hay stock")
    return redirect(url_for('empleado'))


@app.route("/agregar_al_carrito", methods=['POST'])
def agregar_a_carrito():
    global lista_compras
    connection, cursor = get_db()
    cursor.execute("SELECT USER FROM DUAL")
    user = cursor.fetchone()[0]
    cursor.execute(f"SELECT ID FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    id_cliente = cursor.fetchone()[0]
    if request.method == 'POST':
        id = request.form['id']
        cursor.execute("SELECT cantidad FROM SYSTEM.CARRITO_DE_COMPRAS WHERE id_producto = :id AND id_cliente = :id_cliente", id=id, id_cliente=id_cliente)
        resultado = cursor.fetchone()
        if resultado:
         try:
          nueva_cantidad = resultado[0] + 1
          cursor.execute("UPDATE SYSTEM.CARRITO_DE_COMPRAS SET cantidad = :nueva_cantidad WHERE id_producto = :id AND id_cliente = :id_cliente", nueva_cantidad = nueva_cantidad, id=id, id_cliente=id_cliente)
          connection.commit()
         except cx_Oracle.DatabaseError as e:
          print("No hay stock")
        else:
         try:
          cursor.execute("""Insert INTO SYSTEM.CARRITO_DE_COMPRAS (id, id_cliente, id_producto, cantidad)
                            VALUES (system.carrito_seq.NEXTVAL, :id_cliente, :id, 1)
                            """, id_cliente=id_cliente, id=id)
          connection.commit()
         except cx_Oracle.DatabaseError as e:
          print("Error", e)
    return redirect(url_for('cliente'))

@app.route('/carrito_de_compras', methods=['POST', 'GET'])
def ver_carrito():
    datos_cliente = request.form["usuario"]
    cliente_dict = eval(datos_cliente)
    print("datos_cliente: ", datos_cliente)
    print("cliente_dict: ", cliente_dict)
    connection, cursor = get_db()
    cursor.execute("SELECT USER FROM DUAL")
    user = cursor.fetchone()[0]
    cursor.execute(f"SELECT ID, TIPO_DE_USUARIO FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    cliente = cursor.fetchall()
    id_cliente = cliente[0][0]
    tipo_cliente = cliente[0][1]
    cursor.execute("""SELECT system.productos.id, system.productos.precio, system.carrito_de_compras.cantidad, system.productos.nombre
                      FROM system.productos
                      JOIN system.carrito_de_compras ON system.productos.id = system.carrito_de_compras.ID_PRODUCTO
                      WHERE system.carrito_de_compras.ID_CLIENTE = :id_cliente """, id_cliente=id_cliente)
    resultados = cursor.fetchall()
    lista_compras = []
    total = 0
    for resultado in resultados:
       total = total + (resultado[1] * resultado[2])
       dict_compras = {"id": resultado[0], "nombre": resultado[3], "cantidad": resultado[2], "precio": resultado[1], "total": resultado[1] * resultado[2]}
       lista_compras.append(dict_compras)
    return render_template('compras.html', lista_compras=lista_compras, total=total, tipo_usuario=tipo_cliente, usuario=cliente_dict)

@app.route('/agregar_articulo', methods=['POST'])
def agregar_articulo():
    global articulos
    connection, cursor = get_db()
    nombre = request.form['nombre']
    precio = float(request.form['cantidad'])
    cantidad = int(request.form['precio'])
    try:
       cursor.execute("""INSERT INTO SYSTEM.PRODUCTOS (ID, nombre, precio, cantidad)
                         VALUES (system.productos_seq.NEXTVAL, :nombre, :precio, :cantidad)
                      """, nombre=nombre, precio=precio, cantidad=cantidad)
       connection.commit()
    except cx_Oracle.IntegrityError as e:
       connection.rollback()
    return redirect(url_for('auditor'))

@app.route('/eliminar_articulo', methods=['POST'])
def eliminar_articulo():
    global articulos
    connection, cursor = get_db()
    articulo_id = request.form['id']
    try:
       cursor.execute(f"DELETE FROM SYSTEM.PRODUCTOS WHERE ID = {articulo_id}")
       connection.commit()
    except cx_Oracle.IntegrityError as e:
       connection.rollback()
    return redirect(url_for('auditor'))

@app.route('/buscar_articulo', methods=['POST'])
def buscar_articulo():
    connection, cursor = get_db()
    cursor.execute("SELECT ID, NOMBRE, PRECIO, CANTIDAD FROM SYSTEM.PRODUCTOS")
    rows = cursor.fetchall()
    articulos = []
    for row in rows:
      dict_productos = {"id": row[0], "nombre": row[1], "precio": row[2], "cantidad": row[3]}
      articulos.append(dict_productos)
    articulosFiltrados = []
    string = request.form['entrada']
    nombres_medicamentos = [art["nombre"] for art in articulos]
    print(nombres_medicamentos)
    matches = difflib.get_close_matches(string, nombres_medicamentos, n=1, cutoff=0.3) 
    print(matches)
    for art in articulos:
        if art["nombre"] in matches:
            articulosFiltrados.append(art)
    if(string == ''):
     articulosFiltrados = articulos
    return render_template('auditor.html', articulos=articulosFiltrados)

@app.route('/factura', methods=['POST'])
def factura():
    articulos = request.form['articulos']
    total = float(request.form['total'])
    usuario = request.form['usuario']
    usuario_dict = eval(usuario)
    tipo_cliente = request.form['tipo_usuario']
    print("tipo_cliente: ", tipo_cliente)
    articuloList = eval(articulos)
    return render_template("factura.html", articulos=articuloList, tipo_cliente=tipo_cliente, usuario=usuario_dict)

@app.route('/agradecimiento', methods=['POST'])
def gracias():
    tipo_cliente = request.form['tipo_cliente']
    if(tipo_cliente == 'empleado'):
        return render_template("gracias_empleado.html")
    return render_template("gracias.html")

@app.route('/factura_generada', methods=['POST'])
def factura_generada():
    global facturas
    connection, cursor = get_db()
    cursor.execute("SELECT USER FROM DUAL")
    user = cursor.fetchone()[0]
    cursor.execute(f"SELECT ID, TIPO_DE_USUARIO FROM SYSTEM.USUARIOS WHERE NOMBRE_DE_USUARIO = '{user}'")
    columns = cursor.fetchall()
    tipo_usuario = columns[0][1]
    id_usuario = columns[0][0]
    if(tipo_usuario == 'cliente'):
      cursor.execute(f"SELECT ID FROM SYSTEM.CLIENTES WHERE ID_USUARIO = :id_usuario", id_usuario=id_usuario)
      id_cliente = cursor.fetchone()[0]
    guardar = int(request.form['guardar'])
    if(tipo_usuario == 'empleado' or guardar==0):
      rfc = request.form['rfc']
      nombre = request.form['nombre']
      cp = request.form['cp']
      email = request.form['email']
      regimen_fiscal = request.form['regimen_fiscal']
      uso_fiscal = request.form['uso_fiscal']
      if(guardar==0):
       fecha = request.form['fecha']
    else:
      user_data_str = request.form["usuario"]
      user_data = eval(user_data_str)
      print("user data en factura: ", user_data)
      rfc = user_data["rfc"]
      nombre = user_data["nombre"]
      cp = user_data["cp"]
      email = user_data["email"]
      regimen_fiscal = user_data["regimen_fiscal"]
      uso_fiscal = user_data["uso_fiscal"]
    forma_pago = request.form['forma_pago']
    pago = request.form['pago']
    #fecha = request.form['documento_aduanero']
    articulos = request.form['articulos']
    factura_ID = 0
    #id_fac = int(request.form['id_fac'])
    #print("id_fac", id_fac)
    #print("articulos: ",articulos)
    articulosDict = eval(articulos)
    #print("SE GUARDA", guardar)
    if(guardar == 1):
        clave_uuid = None
    else:
        clave_uuid = request.form['uuid']
        articulosDict = []
        factura_ID = int(request.form['id_fac'])
        print("CLAVE UUID: ", clave_uuid)
        cursor.execute("""SELECT system.detalles_factura.cantidad, system.detalles_factura.precio, system.productos.nombre
                          FROM system.detalles_factura
                          JOIN system.productos ON system.detalles_factura.ID_PRODUCTO = system.productos.ID
                          WHERE system.detalles_factura.ID_FACTURA = :factura_ID""", factura_ID=factura_ID)
        rows_art = cursor.fetchall()
        for row in rows_art:
          articulos_dict = {"nombre": row[2], "cantidad": row[0], "precio": row[1], "total": row[1] * row[0]}
          articulosDict.append(articulos_dict)

    total = 0
    for articulo in articulosDict:
      total = total + int(articulo["cantidad"]) * float(articulo["precio"])
    pago_letra = num2words(total, lang='es')
    uuid_fac = cursor.var(cx_Oracle.BINARY)
    if(guardar == 1 and tipo_usuario == 'cliente'):
     print("mirame, estoy guardando :)")
     try:
        id_factura = cursor.var(cx_Oracle.NUMBER)
        fecha = cursor.var(cx_Oracle.Date)
        print("id cliente: ", id_cliente)
        cursor.execute("""INSERT INTO SYSTEM.FACTURAS (ID, ID_CLIENTE, FECHA, forma_de_pago, pago, total)
                          VALUES (system.facturas_seq.NEXTVAL, :id_cliente, SYSDATE, :forma_de_pago, :pago, :total)
                          RETURNING ID, UUID, FECHA INTO :id_factura, :uuid_fac, :fecha
                       """, id_cliente=id_cliente, id_factura=id_factura, uuid_fac=uuid_fac, fecha=fecha, forma_de_pago=forma_pago, pago=pago, total=total)
        factura_ID = id_factura.getvalue()[0]
        print("Factura_ID: ", factura_ID)
        fecha = fecha.getvalue()[0]
        for articulo in articulosDict:
          print("Articulo en insert: ", articulo)
          cursor.execute("""INSERT INTO SYSTEM.DETALLES_FACTURA (ID_FACTURA, ID_PRODUCTO, CANTIDAD, PRECIO)
                            VALUES (:id_factura, :id_producto, :cantidad, :precio)
                            """, id_factura=factura_ID, id_producto = int(articulo["id"]), cantidad=int(articulo["cantidad"]), precio=float(articulo["precio"]))
          cursor.execute("""UPDATE SYSTEM.PRODUCTOS
                            SET cantidad = cantidad - :cantidad
                            WHERE id = :id""", cantidad=int(articulo["cantidad"]), id=int(articulo["id"]))
        cursor.execute("DELETE FROM SYSTEM.CARRITO_DE_COMPRAS WHERE id_cliente = :id_cliente", id_cliente=id_usuario)
        connection.commit()
        uuid_hex = uuid_fac.getvalue()[0].hex()
        clave_uuid = uuid.UUID(uuid_hex)
     except cx_Oracle.DatabaseError as e:
        connection.rollback()
        print("excepcion: ", e)
    if(guardar == 1 and tipo_usuario == 'empleado'):
        for articulo in articulosDict:
          cursor.execute("""UPDATE SYSTEM.PRODUCTOS
                            SET cantidad = cantidad - :cantidad
                            WHERE id = :id""", cantidad=int(articulo["cantidad"]), id=int(articulo["id"]))
        cursor.execute("DELETE FROM SYSTEM.CARRITO_DE_COMPRAS WHERE id_cliente = :id_cliente", id_cliente=id_usuario)
        fecha = datetime.now().strftime('%Y-%m-%d')
        connection.commit()
        cursor.execute("SELECT system.facturas_seq.NEXTVAL from dual")
        factura_ID = cursor.fetchone()[0]
    html = render_template("factura_generada.html", rfc=rfc, nombre=nombre, cp=cp, email=email, regimen_fiscal=regimen_fiscal, uso_fiscal=uso_fiscal, forma_pago=forma_pago, pago=pago, fecha=fecha, articulos=articulosDict, total=total, pago_letra=pago_letra, id_fac=factura_ID, uuid=clave_uuid)
    PDF = HTML(string=html).write_pdf()

    response=send_file(BytesIO(PDF), as_attachment=True, download_name='factura.pdf')
    response.headers["Refresh"] = '5; URL=' + url_for('cliente') 
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)




