from __future__ import annotations
import math
from pathlib import Path
import numpy as np
import pandas as pd

SEED=20260827; DEVELOPMENT_MODE=True; DEVELOPMENT_CUSTOMERS=20_000
END_YEAR=2026; BANK_START=1969; MIN_AGE=18
MIN_CUSTOMERS=90_000; MAX_CUSTOMERS=120_000
rng=np.random.default_rng(SEED)
ROOT=Path(__file__).resolve().parents[1]; BRANCHES=ROOT/'data'/'raw'/'branches.csv'; OUT=ROOT/'data'/'processed'/'customers.csv'

def norm(w):
    a=np.asarray(list(w),dtype=float); s=a.sum()
    if s<=0 or np.any(a<0): raise ValueError('Invalid weights')
    return a/s

def choice(v,w): return rng.choice(list(v),p=norm(w))
def mult(c=1,d=.05): return max(float(rng.normal(c,d)),.05)
def internal(x): return None if pd.isna(x) else x

def lognormal(median,sigma,maximum):
    for _ in range(100):
        x=float(rng.lognormal(math.log(max(median,1)),sigma))
        if 0<=x<=maximum:return round(x,2)
    return round(min(max(x,0),maximum),2)

def load_branches():
    if not BRANCHES.exists(): raise FileNotFoundError(f'branches.csv not found: {BRANCHES}')
    b=pd.read_csv(BRANCHES,dtype={'branch_id':'string'})
    req={'branch_id','department','locality','branch_size','opening_year'}
    miss=req-set(b.columns)
    if miss: raise ValueError(f'branches.csv missing: {sorted(miss)}')
    b['branch_id']=b['branch_id'].astype('string').str.strip().str.zfill(3)
    b['opening_year']=pd.to_numeric(b['opening_year'],errors='raise').astype(int)
    if 'closing_year' not in b:b['closing_year']=pd.NA
    b['closing_year']=pd.to_numeric(b['closing_year'],errors='coerce').astype('Int64')
    return b

# ---------------- names ----------------
# First names are generated through overlapping birth-cohort pools.
# A birth year changes the probability of drawing from OLD / MIDDLE / YOUNG,
# but never makes any cohort impossible. This preserves realistic exceptions
# without assigning a manual probability to every single name.

NAMES={
'URUGUAY':{
'M':{
'OLD':['Juan','José','Carlos','Luis','Jorge','Roberto','Raúl','Ricardo','Héctor','Julio','Mario','Miguel','Alberto','Oscar','Washington','Nelson','Rubén','Eduardo','Enrique','Víctor','Daniel','Fernando','Alejandro','Pablo','Gustavo','Sergio','Marcelo','Gerardo','Alfredo','Hugo'],
'MIDDLE':['Juan','José','Carlos','Luis','Daniel','Fernando','Alejandro','Pablo','Gustavo','Sergio','Marcelo','Diego','Martín','Federico','Andrés','Rodrigo','Gonzalo','Sebastián','Nicolás','Santiago','Matías','Leandro','Leonardo','Gabriel','Adrián','Mauricio','Ignacio','Javier','Fabián','Christian'],
'YOUNG':['Santiago','Nicolás','Matías','Sebastián','Gonzalo','Facundo','Agustín','Bruno','Mateo','Thiago','Benjamín','Valentín','Franco','Joaquín','Tomás','Lautaro','Felipe','Bautista','Lucas','Emiliano','Máximo','Francesco','Juan','Martín','Ignacio','Santino','Dante','Salvador','Ramiro','Simón']},
'F':{
'OLD':['María','Ana','Marta','Susana','Graciela','Beatriz','Teresa','Norma','Mabel','Nélida','Rosa','Elena','Carmen','Gladys','Mirta','Silvia','Alicia','Cristina','Mónica','Liliana','Patricia','Adriana','Laura','Sandra','Claudia','Verónica','Gabriela','Andrea','Virginia','Mariela'],
'MIDDLE':['María','Ana','Laura','Patricia','Adriana','Claudia','Verónica','Gabriela','Andrea','Carolina','Natalia','Paula','Daniela','Mariana','Victoria','Florencia','Lucía','Valeria','Leticia','Lorena','María José','María Eugenia','Soledad','Romina','Cecilia','Pilar','Noelia','Natalia','Agustina','Jimena'],
'YOUNG':['Lucía','Sofía','Valentina','Camila','Florencia','Victoria','Martina','Agustina','Julieta','Micaela','Catalina','Emilia','Josefina','Clara','Delfina','Malena','Renata','Olivia','Emma','Alma','Antonella','Bianca','Juana','Manuela','Pilar','Lola','Amanda','Isabella','Paulina','Zoe']},
'N':['Alex','Ariel','Dani','Noel','Ángel','Cruz','Sam','Andy','Fran','Ale'] ,
'L':['Rodríguez','González','Pereira','Fernández','Martínez','Silva','López','García','Pérez','Sosa','Suárez','Díaz','Acosta','Cabrera','Méndez','Olivera','Viera','Techera','Bentancur','Cardozo','Ferreira','Machado','Moreira','Ramos','Castro','Torres','Gómez','Álvarez','Barrios']},

'ARGENTINA':{
'M':{
'OLD':['Juan','José','Carlos','Luis','Jorge','Roberto','Raúl','Ricardo','Héctor','Julio','Mario','Miguel','Alberto','Oscar','Rubén','Eduardo','Enrique','Víctor','Daniel','Fernando','Alejandro','Pablo','Gustavo','Sergio','Marcelo','Hugo','Horacio','Guillermo','Ernesto','Omar'],
'MIDDLE':['Juan','Martín','Nicolás','Santiago','Matías','Facundo','Federico','Gonzalo','Diego','Pablo','Alejandro','Sebastián','Rodrigo','Andrés','Fernando','Daniel','Gustavo','Ignacio','Javier','Leonardo','Gabriel','Mariano','Leandro','Christian','Damián','Ezequiel','Esteban','Emiliano','Maximiliano','Ramiro'],
'YOUNG':['Santiago','Nicolás','Matías','Facundo','Tomás','Agustín','Franco','Joaquín','Lautaro','Benjamín','Bautista','Thiago','Mateo','Valentín','Santino','Bruno','Lucas','Felipe','Francesco','Máximo','Dante','Salvador','Ramiro','Simón','Emiliano','Juan Cruz','Pedro','Jerónimo','Lorenzo','Benicio']},
'F':{
'OLD':['María','Ana','Marta','Susana','Graciela','Beatriz','Teresa','Norma','Mabel','Rosa','Elena','Carmen','Mirta','Silvia','Alicia','Cristina','Mónica','Liliana','Patricia','Adriana','Laura','Sandra','Claudia','Verónica','Gabriela','Andrea','Virginia','Gloria','Estela','Nora'],
'MIDDLE':['María','Laura','Patricia','Adriana','Claudia','Verónica','Gabriela','Andrea','Carolina','Natalia','Paula','Daniela','Mariana','Victoria','Florencia','Lucía','Valeria','Lorena','Soledad','Romina','Cecilia','Jimena','María Laura','María José','Vanesa','Rocío','Agustina','Julieta','Pilar','Noelia'],
'YOUNG':['Lucía','Sofía','Valentina','Camila','Florencia','Agustina','Martina','Julieta','Catalina','Victoria','Delfina','Josefina','Micaela','Emilia','Malena','Olivia','Renata','Emma','Alma','Antonella','Bianca','Juana','Manuela','Pilar','Lola','Isabella','Zoe','Francesca','Catalina','Uma']},
'N':['Alex','Ariel','Dani','Cruz','Sam','Fran','Andy','Ale'],
'L':['González','Rodríguez','Fernández','López','Martínez','García','Pérez','Sánchez','Romero','Díaz','Álvarez','Torres','Ruiz','Ramírez','Flores','Acosta','Benítez','Herrera']},

'BRAZIL':{
'M':{
'OLD':['José','João','Antônio','Francisco','Carlos','Paulo','Luiz','Manoel','Pedro','Jorge','Roberto','Raimundo','Sebastião','Marcos','Mário','Edson','Paulo César','Cláudio','Sérgio','Ricardo','Fernando','Marcelo','Eduardo','Alexandre','Márcio','Rogério','Renato','André','Fábio','Gilberto'],
'MIDDLE':['Carlos','Paulo','Marcos','Ricardo','Fernando','Marcelo','Eduardo','Alexandre','André','Fábio','Rodrigo','Rafael','Bruno','Felipe','Gustavo','Leonardo','Daniel','Thiago','Vinícius','Leandro','Diego','Renato','Luciano','Márcio','Maurício','Cristiano','Henrique','Anderson','Wagner','Fabiano'],
'YOUNG':['Lucas','Gabriel','Rafael','Bruno','Felipe','Gustavo','Matheus','Thiago','Leonardo','Vinícius','Caio','Pedro','João Pedro','João Vitor','Guilherme','Henrique','Arthur','Miguel','Davi','Bernardo','Heitor','Theo','Enzo','Murilo','Samuel','Nicolas','Matheus','Lucca','Benjamin','Joaquim']},
'F':{
'OLD':['Maria','Ana','Francisca','Antônia','Tereza','Rosa','Aparecida','Lúcia','Marlene','Neusa','Sônia','Fátima','Regina','Célia','Vera','Márcia','Sandra','Cláudia','Denise','Mônica','Cristina','Patrícia','Adriana','Simone','Rosângela','Eliane','Luciana','Solange','Miriam','Helena'],
'MIDDLE':['Ana','Patrícia','Adriana','Simone','Luciana','Juliana','Fernanda','Aline','Camila','Carolina','Mariana','Gabriela','Renata','Daniela','Vanessa','Priscila','Tatiana','Débora','Cristiane','Fabiana','Amanda','Bruna','Beatriz','Larissa','Rafaela','Letícia','Natália','Isabela','Jéssica','Bianca'],
'YOUNG':['Ana','Camila','Amanda','Bruna','Beatriz','Larissa','Mariana','Gabriela','Rafaela','Isabela','Vitória','Luana','Letícia','Carolina','Júlia','Manuela','Laura','Alice','Helena','Valentina','Sophia','Isabella','Heloísa','Lívia','Lorena','Yasmin','Giovanna','Maria Clara','Maria Eduarda','Cecília']},
'N':['Alex','Ariel','Cris','Dani','Sam','Fran','Andy','Noel'],
'L':['Silva','Santos','Oliveira','Souza','Pereira','Costa','Rodrigues','Almeida','Nascimento','Lima','Araújo','Fernandes','Carvalho','Gomes','Martins','Rocha','Ribeiro','Alves','Monteiro','Mendes']},

'VENEZUELA':{
'M':{
'OLD':['José','Luis','Carlos','Jesús','Juan','Miguel','Ángel','Rafael','Antonio','Manuel','Francisco','Ramón','Pedro','Jorge','Roberto','Héctor','Julio','Raúl','Alberto','Eduardo','Ricardo','Víctor','Daniel','Fernando','Alejandro','Orlando','Ernesto','Guillermo','Rodolfo','César'],
'MIDDLE':['José','Luis','Carlos','Jesús','Juan','Miguel','Ángel','Alejandro','Andrés','Daniel','Eduardo','Javier','Ricardo','Víctor','Fernando','Rafael','Leonardo','Gabriel','Manuel','Antonio','Jonathan','Ronald','Wilmer','Alexander','Richard','Omar','Edwin','Franklin','José Luis','José Antonio'],
'YOUNG':['Alejandro','Andrés','Daniel','Eduardo','Javier','Jhon','Jonathan','Yorman','Yeferson','Enderson','Wilmer','Ronald','Deivis','Kevin','Bryan','Anthony','Luis Ángel','José Ángel','Santiago','Samuel','Gabriel','Sebastián','Diego','Adrián','David','Miguel Ángel','Jesús Alejandro','Carlos Eduardo','Ángel David','Mathías']},
'F':{
'OLD':['María','Carmen','Ana','Josefina','Rosa','Luisa','Teresa','Elena','Mercedes','Isabel','Margarita','Gladys','Miriam','Nelly','Aura','Cecilia','Beatriz','Marta','Lucía','Alicia','Yolanda','Irene','Cristina','Patricia','Sandra','Maritza','Nancy','Doris','Virginia','Gloria'],
'MIDDLE':['María','Carmen','Ana','Patricia','Sandra','Daniela','Gabriela','Andrea','Mariana','Alejandra','Paola','Carolina','Natalia','Claudia','Mónica','Adriana','Maritza','Yessica','Katherine','Dayana','Yelitza','Yusmary','Yenifer','Lisandra','Vanessa','Rosangel','Angélica','Johanna','María Fernanda','María Alejandra'],
'YOUNG':['Daniela','Gabriela','Andrea','Valentina','Mariana','Alejandra','Paola','Yessica','Yelitza','Yusmary','Yenifer','Genesis','Orianna','Dayana','Katherine','Rosangel','María José','Sofía','Camila','Isabella','Victoria','Valeria','Nicole','Michelle','Bárbara','Antonella','Fabiana','Ariana','María Victoria','Samantha']},
'N':['Alex','Ángel','Dani','Cris','Sam','Fran','Ariel','Noel'],
'L':['González','Rodríguez','Pérez','Hernández','García','Martínez','López','Sánchez','Ramírez','Torres','Flores','Rojas','Mendoza','Castillo','Romero','Moreno','Suárez','Salazar']},

'CUBA':{
'M':{
'OLD':['José','Luis','Carlos','Juan','Jorge','Miguel','Roberto','Rafael','Manuel','Francisco','Pedro','Ramón','Antonio','Raúl','Orlando','Ernesto','Alberto','Ricardo','Héctor','Julio','Eduardo','Guillermo','Armando','Rolando','Reinaldo','Lázaro','René','Félix','Mario','Víctor'],
'MIDDLE':['José','Luis','Carlos','Juan','Jorge','Miguel','Roberto','Rafael','Alejandro','Daniel','Eduardo','Orlando','Ernesto','Lázaro','Reinier','Yunior','Yosvani','Yordanis','Yasmany','Yoel','Yadier','Yusniel','Dairon','Osmani','Randy','Jorge Luis','Carlos Manuel','Luis Alberto','José Antonio','Juan Carlos'],
'YOUNG':['Alejandro','Daniel','Yunior','Yosvani','Yordanis','Yasmany','Reinier','Yadier','Yusniel','Dairon','Osmani','Randy','Kevin','Bryan','Andy','Adrián','Samuel','Gabriel','David','Carlos Daniel','José Carlos','Luis Ángel','Jorge Luis','Yoel','Yordan','Yuniesky','Yunior Alejandro','Michael','Anthony','Javier']},
'F':{
'OLD':['María','Ana','Caridad','Rosa','Isabel','Carmen','Lourdes','Teresa','Marta','Mercedes','Josefina','Elena','Miriam','Nidia','Gladys','Alicia','Margarita','Irene','Luisa','Ofelia','Silvia','Mabel','Nancy','Dulce','Gloria','Olga','Norma','Martha','Consuelo','Adela'],
'MIDDLE':['María','Ana','Caridad','Yanet','Yadira','Yusimi','Yanelis','Lisandra','Dianelys','Claudia','Laura','Daniela','Dayana','Lourdes','Mabel','Rosa','Isabel','Mariela','Yamila','Yosbelis','Yuleidis','Yenisey','Yudith','Kenia','Mayra','Maritza','Niurka','Yaima','Yamilé','Yordanka'],
'YOUNG':['Yanet','Yadira','Yusimi','Yanelis','Lisandra','Dianelys','Claudia','Laura','Daniela','Dayana','Yamila','Yosbelis','Yuleidis','Yenisey','Yudith','Kenia','Yaima','Yamilé','Yordanka','Gabriela','Valeria','Camila','Sofía','Amanda','Melissa','Nicole','Ariana','Alejandra','María Fernanda','Isabella']},
'N':['Alex','Dani','Ariel','Cris','Sam','Andy','Fran','Noel'],
'L':['Rodríguez','González','Pérez','García','Hernández','Martínez','Díaz','López','Fernández','Sánchez','Torres','Ramírez','Álvarez','Suárez','Castro','Méndez']},

'OTHER':{
'M':{
'OLD':['John','Michael','Robert','David','James','William','Richard','Thomas','Marco','Giuseppe','Antonio','Paolo','Jean','Pierre','Michel','André','Hans','Peter','Mohammed','Omar','Hassan','Ali','George','Edward','Samuel','Daniel','Miguel','Pedro','Carlos','Gabriel'],
'MIDDLE':['Daniel','David','Michael','John','Marco','Luca','Miguel','Pedro','André','Adam','Samir','Omar','Leo','Gabriel','Alex','Christian','Thomas','Martin','Stefan','Nicolas','Julien','Karim','Hassan','Youssef','Paolo','Matteo','Ricardo','Fernando','George','Anthony'],
'YOUNG':['Daniel','David','Michael','Luca','Matteo','Leo','Gabriel','Adam','Samir','Omar','Alex','Noah','Liam','Ethan','Oliver','Lucas','Theo','Nathan','Nicolas','Julian','Max','Leo','Youssef','Amir','Karim','Enzo','Milan','Samuel','Benjamin','Adrian']},
'F':{
'OLD':['Anna','Maria','Anne','Marie','Susan','Margaret','Elizabeth','Linda','Patricia','Barbara','Giulia','Rosa','Sofia','Isabel','Carmen','Fatima','Amina','Nadia','Helena','Eva','Monica','Claudia','Christine','Teresa','Francesca','Laura','Carla','Elena','Sara','Julia'],
'MIDDLE':['Anna','Sara','Laura','Sofia','Maya','Julia','Nadia','Carla','Elena','Amina','Isabel','Gabriela','Monica','Claudia','Christine','Francesca','Giulia','Silvia','Daniela','Natalia','Vanessa','Samira','Leila','Fatima','Diana','Andrea','Nicole','Marina','Victoria','Cecilia'],
'YOUNG':['Anna','Sara','Sofia','Maya','Julia','Emma','Nadia','Amina','Lucía','Isabel','Gabriela','Olivia','Mia','Amelia','Emily','Lina','Leila','Yasmin','Nora','Eva','Elena','Giulia','Sofia','Chloe','Zoe','Layla','Hana','Alice','Clara','Isabella']},
'N':['Alex','Sam','Noel','Ariel','Dani','Andy','Fran','Charlie','Taylor','Robin'],
'L':['Smith','Rossi','Bianchi','Martins','Costa','García','Müller','Martin','Bernard','Khan','Hassan','Kim','Lee','Chen','Wang']}}


def name_cohort_weights(birth_year):
    """Return overlapping cohort probabilities conditioned on birth year."""
    if birth_year <= 1955:
        return {'OLD':.82,'MIDDLE':.16,'YOUNG':.02}
    if birth_year <= 1965:
        return {'OLD':.68,'MIDDLE':.29,'YOUNG':.03}
    if birth_year <= 1975:
        return {'OLD':.42,'MIDDLE':.53,'YOUNG':.05}
    if birth_year <= 1985:
        return {'OLD':.20,'MIDDLE':.68,'YOUNG':.12}
    if birth_year <= 1995:
        return {'OLD':.08,'MIDDLE':.62,'YOUNG':.30}
    if birth_year <= 2000:
        return {'OLD':.05,'MIDDLE':.47,'YOUNG':.48}
    return {'OLD':.025,'MIDDLE':.275,'YOUNG':.70}


def person_name(nat,gender,birth):
    p=NAMES.get(nat,NAMES['OTHER'])

    # Most unspecified-gender records use a neutral pool. For auditing,
    # those cases are labelled NEUTRAL rather than forcing them into a cohort.
    if gender=='OTHER_OR_UNSPECIFIED' and rng.random()<.70:
        first=str(rng.choice(p['N']))
        cohort='NEUTRAL'
    else:
        key='F' if gender=='FEMALE' else 'M' if gender=='MALE' else str(choice(['F','M'],[.5,.5]))
        cw=name_cohort_weights(birth)
        cohort=str(choice(cw.keys(),cw.values()))
        pool=p[key][cohort]

        # Mild within-pool rank weighting creates common and less-common names
        # without requiring a hand-coded probability for every name.
        fw=np.linspace(1.45,.70,len(pool))
        first=str(choice(pool,fw))

    # Surnames remain non-uniform and may be compound.
    lw=np.linspace(1.65,.70,len(p['L']))
    last=str(choice(p['L'],lw))
    if rng.random()<.16:
        second=str(choice(p['L'],lw))
        last=last if second==last else f'{last} {second}'
    return first,last,cohort

# ---------------- geography ----------------
DW={'Montevideo':34,'Canelones':16,'Maldonado':6,'Salto':4,'Colonia':4,'Paysandú':3.5,'San José':3.3,'Rivera':3.2,'Tacuarembó':2.8,'Cerro Largo':2.7,'Soriano':2.5,'Artigas':2.3,'Rocha':2.3,'Florida':2.1,'Lavalleja':1.8,'Durazno':1.8,'Río Negro':1.6,'Treinta y Tres':1.5,'Flores':.8}
LOC={
'Montevideo':{'Montevideo':1.00},
'Canelones':{'Ciudad de la Costa':.24,'Las Piedras':.20,'Pando':.12,'Canelones':.09,'La Paz':.08,'Santa Lucía':.07,'Atlántida':.06,'Progreso':.05,'Sauce':.04,'Toledo':.05},
'Maldonado':{'Maldonado':.31,'Punta del Este':.20,'San Carlos':.17,'Piriápolis':.12,'Pan de Azúcar':.07,'Aiguá':.04,'Solís':.03,'La Barra':.03,'Punta Ballena':.03},
'Treinta y Tres':{'Treinta y Tres':.57,'Vergara':.15,'Santa Clara de Olimar':.08,'La Charqueada':.07,'Cerro Chato':.06,'Rincón':.03,'General Enrique Martínez':.04},
'Cerro Largo':{'Melo':.55,'Río Branco':.22,'Aceguá':.06,'Fraile Muerto':.06,'Isidoro Noblía':.04,'Tupambaé':.03,'Plácido Rosas':.02,'Arévalo':.02},
'Rocha':{'Rocha':.29,'Chuy':.19,'La Paloma':.14,'Castillos':.12,'Lascano':.10,'La Pedrera':.05,'Cebollatí':.04,'Velázquez':.04,'Aguas Dulces':.03},
'Lavalleja':{'Minas':.68,'José Pedro Varela':.14,'Solís de Mataojo':.07,'Mariscala':.05,'Pirarajá':.03,'Zapicán':.03},
'Artigas':{'Artigas':.68,'Bella Unión':.23,'Tomás Gomensoro':.05,'Baltasar Brum':.04},
'Rivera':{'Rivera':.72,'Tranqueras':.12,'Vichadero':.07,'Minas de Corrales':.06,'Masoller':.03},
'Salto':{'Salto':.83,'Constitución':.06,'Belén':.05,'San Antonio':.03,'Colonia Lavalleja':.03},
'Paysandú':{'Paysandú':.78,'Guichón':.09,'Quebracho':.06,'Porvenir':.04,'Piedras Coloradas':.03},
'Río Negro':{'Fray Bentos':.54,'Young':.30,'Nuevo Berlín':.08,'San Javier':.05,'Algorta':.03},
'Soriano':{'Mercedes':.54,'Dolores':.23,'Cardona':.10,'José Enrique Rodó':.06,'Palmitas':.04,'Villa Soriano':.03},
'Colonia':{'Colonia del Sacramento':.29,'Carmelo':.18,'Nueva Helvecia':.13,'Juan Lacaze':.11,'Rosario':.10,'Nueva Palmira':.08,'Tarariras':.06,'Colonia Valdense':.05},
'San José':{'San José de Mayo':.40,'Ciudad del Plata':.27,'Libertad':.14,'Ecilda Paullier':.07,'Rodríguez':.06,'Rafael Perazza':.03,'Puntas de Valdez':.03},
'Florida':{'Florida':.63,'Sarandí Grande':.17,'Casupá':.07,'Fray Marcos':.06,'25 de Mayo':.04,'Cardal':.03},
'Durazno':{'Durazno':.66,'Sarandí del Yí':.17,'Villa del Carmen':.06,'La Paloma':.04,'Carlos Reyles':.04,'Centenario':.03},
'Flores':{'Trinidad':.82,'Ismael Cortinas':.10,'Andresito':.05,'La Casilla':.03},
'Tacuarembó':{'Tacuarembó':.66,'Paso de los Toros':.19,'San Gregorio de Polanco':.06,'Ansina':.04,'Curtina':.03,'Achar':.02}}

BORDER={'Chuy','Rivera','Río Branco','Aceguá','Artigas','Bella Unión'}

def nationality():
    if rng.random()<rng.uniform(.85,.94):return 'URUGUAY'
    return choice(['ARGENTINA','BRAZIL','VENEZUELA','CUBA','OTHER'],[rng.uniform(.18,.28),rng.uniform(.22,.34),rng.uniform(.16,.27),rng.uniform(.05,.12),rng.uniform(.08,.16)])

def gender():
    o=rng.uniform(.005,.025); f=rng.uniform(.47,.53)
    return choice(['FEMALE','MALE','OTHER_OR_UNSPECIFIED'],[(1-o)*f,(1-o)*(1-f),o])

def residence_country(ctype,nat):
    p=rng.uniform(.005,.025) if ctype=='BUSINESS' else rng.uniform(.015,.045)
    if nat in {'ARGENTINA','BRAZIL'}:p*=1.6
    return 'URUGUAY' if rng.random()>=min(p,.15) else choice(['ARGENTINA','BRAZIL','SPAIN','USA','OTHER'],[.30,.28,.15,.12,.15])

def uy_residence(nat):
    deps=list(DW); ws=[]
    for d in deps:
        w=DW[d]*({'Treinta y Tres':2.5,'Cerro Largo':1.65,'Rocha':1.4,'Lavalleja':1.2,'Maldonado':1.15,'Montevideo':1.05,'Canelones':1.05}.get(d,1))
        if nat=='BRAZIL' and d in {'Rivera','Cerro Largo','Artigas','Rocha'}:w*=3
        if nat=='ARGENTINA' and d in {'Colonia','Soriano','Río Negro','Paysandú','Salto'}:w*=2
        if nat=='ARGENTINA' and d=='Maldonado':w*=2.2
        if nat in {'VENEZUELA','CUBA'}:w*=3 if d=='Montevideo' else 1.6 if d=='Canelones' else 1.3 if d=='Maldonado' else 1
        ws.append(w*rng.lognormal(0,.08))
    d=str(choice(deps,ws)); l=str(choice(LOC[d].keys(),LOC[d].values())); return d,l

# ---------------- economics ----------------
def birth_year():
    b=choice(['18_24','25_34','35_49','50_64','65_79','80_95'],[.08,.21,.31,.24,.13,.03]); lo,hi={'18_24':(18,24),'25_34':(25,34),'35_49':(35,49),'50_64':(50,64),'65_79':(65,79),'80_95':(80,95)}[b]; return END_YEAR-int(rng.integers(lo,hi+1))
def foundation_year():
    b=choice(['0_5','6_10','11_20','21_35','36_55','56_80','81_110'],[.22,.19,.24,.18,.11,.05,.01]); lo,hi={'0_5':(0,5),'6_10':(6,10),'11_20':(11,20),'21_35':(21,35),'36_55':(36,55),'56_80':(56,80),'81_110':(81,110)}[b]; return max(1900,END_YEAR-int(rng.integers(lo,hi+1)))
def employment(age):
    if age<=24:w={'EMPLOYED':.42,'SELF_EMPLOYED':.08,'UNEMPLOYED':.12,'RETIRED':.001,'STUDENT':.34,'OTHER':.039}
    elif age<=34:w={'EMPLOYED':.62,'SELF_EMPLOYED':.17,'UNEMPLOYED':.09,'RETIRED':.002,'STUDENT':.08,'OTHER':.038}
    elif age<=49:w={'EMPLOYED':.66,'SELF_EMPLOYED':.20,'UNEMPLOYED':.07,'RETIRED':.01,'STUDENT':.015,'OTHER':.045}
    elif age<=59:w={'EMPLOYED':.61,'SELF_EMPLOYED':.20,'UNEMPLOYED':.07,'RETIRED':.07,'STUDENT':.005,'OTHER':.045}
    elif age<=69:w={'EMPLOYED':.28,'SELF_EMPLOYED':.14,'UNEMPLOYED':.04,'RETIRED':.49,'STUDENT':.002,'OTHER':.048}
    else:w={'EMPLOYED':.06,'SELF_EMPLOYED':.05,'UNEMPLOYED':.01,'RETIRED':.82,'STUDENT':.001,'OTHER':.059}
    return choice(w.keys(),w.values())
def profile(e,d,l):
    if e=='EMPLOYED':p={'LONG_TENURE_SALARIED':.62,'VARIABLE_SALARIED':.25,'AGRICULTURAL_WORKER':.06,'TOURISM_WORKER':.04,'SEASONAL_SERVICE_WORKER':.03}
    elif e=='SELF_EMPLOYED':p={'INDEPENDENT_PROFESSIONAL':.32,'SMALL_RETAILER':.29,'AGRICULTURAL_PRODUCER':.20,'BORDER_TRADER':.08,'SEASONAL_SERVICE_WORKER':.11}
    elif e=='UNEMPLOYED':p={'UNEMPLOYED_IRREGULAR':.88,'SEASONAL_SERVICE_WORKER':.12}
    elif e=='RETIRED':p={'RETIRED_STABLE':1}
    elif e=='STUDENT':p={'STUDENT_DEPENDENT':1}
    else:p={'OTHER_INDIVIDUAL':1}
    if 'AGRICULTURAL_PRODUCER'in p and d not in {None,'Montevideo'}:p['AGRICULTURAL_PRODUCER']*=1.8
    if 'AGRICULTURAL_WORKER'in p and d not in {None,'Montevideo'}:p['AGRICULTURAL_WORKER']*=1.7
    if 'TOURISM_WORKER'in p and d in {'Maldonado','Rocha'}:p['TOURISM_WORKER']*=3
    if 'BORDER_TRADER'in p:p['BORDER_TRADER']*=5 if l in BORDER else .1
    return choice(p.keys(),p.values())
INC={'STUDENT_DEPENDENT':(24000,.65),'UNEMPLOYED_IRREGULAR':(29000,.70),'RETIRED_STABLE':(45000,.38),'AGRICULTURAL_WORKER':(52000,.45),'TOURISM_WORKER':(54000,.60),'SEASONAL_SERVICE_WORKER':(48000,.62),'LONG_TENURE_SALARIED':(68000,.38),'VARIABLE_SALARIED':(65000,.52),'SMALL_RETAILER':(72000,.65),'BORDER_TRADER':(72000,.78),'INDEPENDENT_PROFESSIONAL':(95000,.72),'AGRICULTURAL_PRODUCER':(100000,.85),'OTHER_INDIVIDUAL':(45000,.60)}
def income(p,age,d):
    med,s=INC[p]; med*=mult(.88 if age<=24 else 1 if age<=34 else 1.07 if age<=49 else 1.05 if age<=59 else 1,.06); med*=mult(1 if d is None or p=='AGRICULTURAL_PRODUCER' else 1.08 if d=='Montevideo' else 1.02 if d=='Canelones' else 1.03 if d=='Maldonado' else 1,.07 if d is None or d=='Maldonado' else .05); return lognormal(med,s,5_000_000)
SECT={'AGRICULTURE':.15,'COMMERCE':.27,'TOURISM_HOSPITALITY':.06,'INDUSTRY':.08,'CONSTRUCTION':.09,'TRANSPORT_LOGISTICS':.08,'PROFESSIONAL_SERVICES':.11,'TECHNOLOGY':.04,'HEALTH_EDUCATION':.05,'OTHER_SERVICES':.07}
def sector(d,l):
    w=SECT.copy()
    if d not in {None,'Montevideo'}:w['AGRICULTURE']*=1.5
    if d in {'Treinta y Tres','Cerro Largo','Rocha'}:w['AGRICULTURE']*=1.4
    if d in {'Maldonado','Rocha'}:w['TOURISM_HOSPITALITY']*=2.7
    if d in {'Montevideo','Canelones'}:w['PROFESSIONAL_SERVICES']*=1.6;w['TECHNOLOGY']*=1.8
    if l in BORDER:w['COMMERCE']*=1.5;w['TRANSPORT_LOGISTICS']*=1.6
    return choice(w.keys(),w.values())
def subprofile(s,l):
    pools={'AGRICULTURE':{'CATTLE':.31,'DAIRY':.13,'RICE':.13,'SOY':.16,'CITRUS':.08,'FORESTRY':.08,'MIXED':.11},'COMMERCE':{'GENERAL_RETAIL':.34,'FOOD_RETAIL':.20,'WHOLESALE':.14,'BORDER_COMMERCE':.07,'TECHNOLOGY_RETAIL':.10,'VEHICLE_RELATED':.15},'TOURISM_HOSPITALITY':{'ACCOMMODATION':.30,'GASTRONOMY':.45,'TOURISM_SERVICES':.25},'TRANSPORT_LOGISTICS':{'DOMESTIC_TRANSPORT':.45,'FREIGHT':.40,'PORT_LOGISTICS':.15}}
    if s not in pools:return s
    w=pools[s].copy()
    if s=='COMMERCE':w['BORDER_COMMERCE']*=5 if l in BORDER else .12
    return choice(w.keys(),w.values())
def company_size(s,fy,d):
    w={'MICRO':rng.uniform(55,70),'SMALL':rng.uniform(20,32),'MEDIUM':rng.uniform(5,12),'LARGE':rng.uniform(.5,3)}
    if s in {'COMMERCE','PROFESSIONAL_SERVICES','OTHER_SERVICES'}:w['MICRO']*=1.18;w['SMALL']*=1.08;w['MEDIUM']*=.85;w['LARGE']*=.7
    if s in {'AGRICULTURE','INDUSTRY','TRANSPORT_LOGISTICS'}:w['MICRO']*=.82;w['MEDIUM']*=1.45;w['LARGE']*=2
    age=END_YEAR-fy
    if age<=5:w['MICRO']*=1.35;w['SMALL']*=1.1;w['MEDIUM']*=.7;w['LARGE']*=.45
    elif age>=30:w['MICRO']*=.85;w['MEDIUM']*=1.25;w['LARGE']*=1.55
    return choice(w.keys(),w.values())
PREFIX={'AGRICULTURE':['Agropecuaria','Establecimiento','Campos','Agro','Ganadera'],'COMMERCE':['Comercial','Distribuidora','Mercado','Barraca'],'TOURISM_HOSPITALITY':['Posada','Hotel','Parador','Servicios Turísticos'],'INDUSTRY':['Industrias','Industrial','Manufacturas'],'CONSTRUCTION':['Construcciones','Constructora','Obras'],'TRANSPORT_LOGISTICS':['Transportes','Logística','Cargas'],'PROFESSIONAL_SERVICES':['Estudio','Consultora','Asesores'],'TECHNOLOGY':['Sistemas','Tech','Data','Digital'],'HEALTH_EDUCATION':['Centro','Servicios','Instituto'],'OTHER_SERVICES':['Servicios','Soluciones','Grupo']}
def company_name(s,sp,size,d,l):
    pre=str(rng.choice(PREFIX[s])); family=NAMES['URUGUAY']['L']+NAMES['BRAZIL']['L']
    if sp=='RICE':pre=str(choice(['Arrozal','Agropecuaria','Campos'],[.5,.3,.2]))
    elif sp=='CATTLE':pre=str(choice(['Ganadera','Establecimiento','Agropecuaria'],[.45,.35,.2]))
    elif sp=='DAIRY':pre=str(choice(['Tambo','Lácteos','Establecimiento'],[.45,.3,.25]))
    elif sp=='BORDER_COMMERCE':pre=str(choice(['Comercial','Importadora','Distribuidora'],[.5,.2,.3]))
    elif sp=='ACCOMMODATION':pre=str(choice(['Hotel','Posada','Hostería'],[.45,.4,.15]))
    elif sp=='GASTRONOMY':pre=str(choice(['Restaurante','Parador','Sabores'],[.45,.3,.25]))
    if rng.random() < (.52 if size in {'MICRO','SMALL'} else .25): name=f'{pre} {rng.choice(family)}'
    else:name=f"{pre} {l if l and not str(l).startswith('Other ') and rng.random()<.25 else rng.choice(['del Este','del Plata','Oriental','del Olimar','del Norte','del Sur','Uruguay'])}"
    if size=='LARGE' and rng.random()<.55:name+=' S.A.'
    elif size in {'SMALL','MEDIUM'} and rng.random()<.2:name+=' Ltda.'
    return name
REV={'MICRO':(4_500_000,.90),'SMALL':(17_000_000,.85),'MEDIUM':(70_000_000,.90),'LARGE':(350_000_000,1.0)}; RM={'AGRICULTURE':1.25,'COMMERCE':1.10,'TOURISM_HOSPITALITY':.95,'INDUSTRY':1.30,'CONSTRUCTION':1.15,'TRANSPORT_LOGISTICS':1.20,'PROFESSIONAL_SERVICES':.85,'TECHNOLOGY':1,'HEALTH_EDUCATION':.95,'OTHER_SERVICES':.8}
def revenue(size,s,fy):
    med,sg=REV[size];med*=RM[s];age=END_YEAR-fy
    med*=mult(.78,.15) if age<=3 else mult(.93,.12) if age<=10 else mult(1.1,.15) if age>=30 else 1;med*=.7+float(np.clip(rng.normal(.5,.15),0,1))*.6;return lognormal(med,sg,100_000_000_000)

# ---------------- documents/history/branches ----------------
def doc_type(ct,nat,country):
    if ct=='BUSINESS':return 'RUT'
    if nat=='URUGUAY':return 'CI'
    if country=='URUGUAY' and rng.random()<.28:return 'CI'
    return choice(['PASSPORT','FOREIGN_ID'],[.55,.45])
def unique_doc(fn,used):
    while True:
        x=fn()
        if x not in used:used.add(x);return x
def doc_id(t,birth,used):
    if t=='CI':
        age=END_YEAR-int(birth);lo,hi=(800000,3400000) if age>=80 else (1000000,4200000) if age>=65 else (1500000,4800000) if age>=50 else (2500000,5500000) if age>=35 else (3500000,5900000) if age>=25 else (4500000,6000000);return unique_doc(lambda:f'CI{int(rng.integers(lo,hi+1)):07d}',used)
    letters=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    if t=='PASSPORT':return unique_doc(lambda:'P'+''.join(rng.choice(letters,2))+str(int(rng.integers(1_000_000,10_000_000))),used)
    if t=='FOREIGN_ID':return unique_doc(lambda:'F'+''.join(rng.choice(letters,2))+str(int(rng.integers(10_000_000,100_000_000))),used)
    return unique_doc(lambda:f'RUT{int(rng.integers(10_000_000_000,100_000_000_000))}',used)
def shocks():
    d={};prev=0
    for y in range(BANK_START,END_YEAR+1):prev=.72*prev+rng.normal(0,.08);d[y]=math.exp(prev)
    return d
def reg_year(ct,birth,fy,nat,b,sh):
    earliest=max(BANK_START,int(birth)+MIN_AGE) if ct=='INDIVIDUAL' else max(BANK_START,int(fy)); years=np.arange(min(earliest,END_YEAR),END_YEAR+1);ws=[]
    for y0 in years:
        y=int(y0);w=max(len(b[b.opening_year<=y]),1)**.6*(.65+(y-BANK_START)/100)*sh[y]
        if ct=='INDIVIDUAL':
            if nat=='VENEZUELA':w*=.08 if y<2010 else .35 if y<=2016 else 1.4 if y<=2020 else 2.5
            elif nat=='CUBA':w*=.15 if y<2005 else .5 if y<=2014 else 1.25 if y<=2020 else 2
            ja=y-int(birth);w*=1.25 if ja<=24 else 1.15 if ja<=39 else 1 if ja<=59 else .75
        else:
            delay=y-int(fy);w*=1.2 if delay<=3 else 1.05 if delay<=10 else .8 if delay>=30 else 1
        ws.append(w)
    return int(choice(years,ws))
def historical_res(country,d,l,reg):
    if country!='URUGUAY':return country,None,None
    if rng.random()>min(.04+(END_YEAR-reg)*.006,.28):return 'URUGUAY',d,l
    deps=list(DW);ws=[DW[x]*(4 if x==d else 1)*(1.5 if x=='Montevideo' else 1) for x in deps];hd=str(choice(deps,ws));return 'URUGUAY',hd,str(choice(LOC[hd].keys(),LOC[hd].values()))
# Broad geographic regions used only to structure branch-choice probabilities.
# The category is selected first and the specific branch second, which prevents
# many distant branches from collectively overpowering one nearby branch.
DEPARTMENT_REGION={
    'Montevideo':'METRO',
    'Canelones':'METRO',
    'San José':'METRO',
    'Maldonado':'EAST',
    'Rocha':'EAST',
    'Lavalleja':'EAST',
    'Treinta y Tres':'EAST',
    'Cerro Largo':'EAST',
    'Colonia':'LITORAL',
    'Soriano':'LITORAL',
    'Río Negro':'LITORAL',
    'Paysandú':'LITORAL',
    'Salto':'LITORAL',
    'Artigas':'NORTH',
    'Rivera':'NORTH',
    'Tacuarembó':'NORTH',
    'Durazno':'CENTER',
    'Flores':'CENTER',
    'Florida':'CENTER',
}


def _choose_branch_inside(pool,reg):
    """Choose one branch from an already-selected geographic pool."""
    ws=[]
    east={'Treinta y Tres','Cerro Largo','Rocha','Lavalleja','Maldonado'}

    for _,r in pool.iterrows():
        w={'SMALL':1.00,'MEDIUM':1.15,'LARGE':1.30}.get(
            str(r.branch_size).upper(),1.00
        )

        # Older established offices have a mild relationship advantage.
        w*=1+min(reg-int(r.opening_year),30)*.015

        # BTYT has a modest structural franchise advantage in its eastern core.
        if r.department in east:
            w*=1.12

        # Idiosyncratic customer-level noise prevents deterministic allocation.
        w*=rng.lognormal(0,.18)
        ws.append(w)

    idx=rng.choice(pool.index.to_numpy(),p=norm(ws))
    return pool.loc[idx,'branch_id']


def primary_branch(reg,country,d,l,b):
    """
    Select the primary branch in two stages:

    1) choose a geographic relationship category;
    2) choose a concrete branch inside that category.

    This avoids the old "many distant branches" problem, where dozens of small
    external weights could collectively dominate one local office.
    """
    eligible=b[
        (b.opening_year<=reg)
        & (b.closing_year.isna() | (b.closing_year>=reg))
    ].copy()

    if eligible.empty:
        raise RuntimeError(f'No eligible branch for registration year {reg}')

    # Non-residents remain plausibly tied to large/metro or eastern offices.
    if country!='URUGUAY':
        metro=eligible[eligible.department.isin({'Montevideo','Canelones'})]
        east=eligible[eligible.department.isin(
            {'Treinta y Tres','Cerro Largo','Rocha','Lavalleja','Maldonado'}
        )]
        other=eligible[
            ~eligible.index.isin(metro.index)
            & ~eligible.index.isin(east.index)
        ]

        pools=[]
        weights=[]
        if not metro.empty:
            pools.append(metro); weights.append(.62)
        if not east.empty:
            pools.append(east); weights.append(.25)
        if not other.empty:
            pools.append(other); weights.append(.13)

        selected_pool=pools[int(rng.choice(
            np.arange(len(pools)),
            p=norm(weights)
        ))]
        return _choose_branch_inside(selected_pool,reg)

    # Uruguay resident: historical residence at registration drives the
    # relationship, not necessarily current residence.
    region=DEPARTMENT_REGION.get(d)

    local=eligible[
        (eligible.department==d)
        & (eligible.locality==l)
    ]

    same_department=eligible[
        (eligible.department==d)
        & ~eligible.index.isin(local.index)
    ]

    same_region=eligible[
        eligible.department.map(DEPARTMENT_REGION).eq(region)
        & (eligible.department!=d)
    ] if region is not None else eligible.iloc[0:0]

    # Metro relationships remain possible for customers from the interior.
    metro=eligible[
        eligible.department.isin({'Montevideo','Canelones'})
        & ~eligible.index.isin(local.index)
        & ~eligible.index.isin(same_department.index)
        & ~eligible.index.isin(same_region.index)
    ]

    used_idx=set(local.index) | set(same_department.index) | set(same_region.index) | set(metro.index)
    other=eligible[~eligible.index.isin(used_idx)]

    # Category probabilities depend on the actual coverage available.
    # They are renormalized after unavailable categories are removed.
    if not local.empty:
        category_weights={
            'LOCAL':.72,
            'SAME_DEPARTMENT':.15,
            'SAME_REGION':.07,
            'METRO':.04,
            'OTHER':.02,
        }
    elif not same_department.empty:
        category_weights={
            'SAME_DEPARTMENT':.75,
            'SAME_REGION':.12,
            'METRO':.08,
            'OTHER':.05,
        }
    else:
        # Departments without an office naturally produce more cross-department
        # banking, but still favor geographically coherent regional ties.
        category_weights={
            'SAME_REGION':.55,
            'METRO':.30,
            'OTHER':.15,
        }

    category_pools={
        'LOCAL':local,
        'SAME_DEPARTMENT':same_department,
        'SAME_REGION':same_region,
        'METRO':metro,
        'OTHER':other,
    }

    available=[
        k for k in category_weights
        if not category_pools[k].empty
    ]

    # Defensive fallback: should be unreachable if eligible is non-empty.
    if not available:
        return _choose_branch_inside(eligible,reg)

    selected_category=str(choice(
        available,
        [category_weights[k] for k in available]
    ))

    return _choose_branch_inside(
        category_pools[selected_category],
        reg
    )

def lifecycle(reg,bid,b):
    p=(1-(1-.035)**max(END_YEAR-reg,1))*rng.uniform(.75,1.25);br=b[b.branch_id==bid].iloc[0];bc=br.closing_year;p*=1.18 if pd.notna(bc) else 1;p=min(float(p),.55)
    if rng.random()>=p:return 'ACTIVE',pd.NA
    ys=np.arange(reg,END_YEAR+1);w=.35+np.sqrt(ys-reg+1)
    if pd.notna(bc):w=np.array([x*(1.15 if y>=int(bc) else 1) for x,y in zip(w,ys)])
    return 'CLOSED',int(choice(ys,w))

# ---------------- generation / validation ----------------
COLS=['customer_id','customer_type','first_name','last_name','company_name','nationality','document_type','document_id','birth_year','gender','residence_country','residence_department','residence_locality','primary_branch_id','registration_year','customer_status','closing_year','employment_status','monthly_income','business_sector','company_size','foundation_year','annual_revenue']
def generate():
    print('=== BTYT CUSTOMER GENERATOR ===\nLoading branch master...')
    b=load_branches()
    sh=shocks()
    n=DEVELOPMENT_CUSTOMERS if DEVELOPMENT_MODE else int(rng.integers(MIN_CUSTOMERS,MAX_CUSTOMERS+1))
    share=rng.uniform(.08,.15)
    types=rng.choice(['INDIVIDUAL','BUSINESS'],n,p=[1-share,share])
    used=set()
    rows=[]
    audit_name_cohorts=[]

    print(f"Mode: {'DEVELOPMENT' if DEVELOPMENT_MODE else 'FINAL'}")
    print(f'Generating {n:,} customers...')

    for i,ct in enumerate(types):
        if ct=='INDIVIDUAL':
            by=birth_year()
            fy=pd.NA
            nat=nationality()
            g=gender()
            fn,ln,name_cohort=person_name(nat,g,by)
            cn=pd.NA
            age=END_YEAR-by
        else:
            by=pd.NA
            fy=foundation_year()
            nat=pd.NA
            g=pd.NA
            fn=ln=pd.NA
            name_cohort=pd.NA
            cn=None
            age=None

        ni=internal(nat)
        country=residence_country(ct,ni)
        if country=='URUGUAY':
            dep,loc=uy_residence(ni)
        else:
            dep=loc=pd.NA

        di,li=internal(dep),internal(loc)

        if ct=='INDIVIDUAL':
            emp=employment(age)
            pr=profile(emp,di,li)
            mi=income(pr,age,di)
            bs=cs=ar=pd.NA
        else:
            emp=mi=pd.NA
            bs=sector(di,li)
            sp=subprofile(bs,li)
            cs=company_size(bs,int(fy),di)
            cn=company_name(bs,sp,cs,di,li)
            ar=revenue(cs,bs,int(fy))

        dt=doc_type(ct,ni,country)
        did=doc_id(dt,by,used)
        reg=reg_year(ct,by,fy,ni,b,sh)
        hc,hd,hl=historical_res(country,di,li,reg)
        bid=primary_branch(reg,hc,hd,hl,b)
        status,close=lifecycle(reg,bid,b)

        rows.append([
            f'C{i+1:07d}',ct,fn,ln,cn,nat,dt,did,by,g,country,dep,loc,
            bid,reg,status,close,emp,mi,bs,cs,fy,ar
        ])
        audit_name_cohorts.append(name_cohort)

        if DEVELOPMENT_MODE and (i+1)%20000==0:
            print(f'  ... {i+1:,}/{n:,}')

    df=pd.DataFrame(rows,columns=COLS)
    for c in ['birth_year','foundation_year','closing_year']:
        df[c]=df[c].astype('Int64')
    for c in ['monthly_income','annual_revenue']:
        df[c]=pd.to_numeric(df[c],errors='coerce').astype('Float64')
    df['primary_branch_id']=df['primary_branch_id'].astype('string').str.zfill(3)

    # Internal audit-only field. It is removed before customers.csv is saved.
    df['_name_cohort']=pd.Series(audit_name_cohorts,dtype='string')
    return df,b

def validate(df,b):
    err=[];ind=df[df.customer_type=='INDIVIDUAL'];bus=df[df.customer_type=='BUSINESS']
    if not .85<=len(ind)/len(df)<=.92:err.append('customer_type share')
    if df.customer_id.duplicated().any() or df.document_id.duplicated().any():err.append('duplicate IDs')
    if ind[['first_name','last_name']].isna().any().any() or ind.company_name.notna().any():err.append('individual name structure')
    if bus.first_name.notna().any() or bus.last_name.notna().any() or bus.company_name.isna().any():err.append('business name structure')
    for c in ['nationality','birth_year','gender','employment_status','monthly_income']:
        if ind[c].isna().any() or bus[c].notna().any():err.append(c)
    for c in ['business_sector','company_size','foundation_year','annual_revenue']:
        if bus[c].isna().any() or ind[c].notna().any():err.append(c)
    if (ind.registration_year<ind.birth_year+18).any() or (bus.registration_year<bus.foundation_year).any():err.append('registration chronology')
    if df[df.customer_status=='ACTIVE'].closing_year.notna().any() or df[df.customer_status=='CLOSED'].closing_year.isna().any():err.append('lifecycle')
    uy=df[df.residence_country=='URUGUAY'];ab=df[df.residence_country!='URUGUAY']
    if uy.residence_department.isna().any() or uy.residence_locality.isna().any() or ab.residence_department.notna().any() or ab.residence_locality.notna().any():err.append('geography')
    valid_pairs={(d,l) for d,locs in LOC.items() for l in locs}
    if any((d,l) not in valid_pairs for d,l in zip(uy.residence_department,uy.residence_locality)):err.append('invalid department/locality pair')
    if not b.branch_id.str.fullmatch(r'\d{3}').all() or not df.primary_branch_id.str.fullmatch(r'\d{3}').all():err.append('branch_id format')
    if df.monthly_income.dtype.name!='Float64' or df.annual_revenue.dtype.name!='Float64':err.append('financial dtypes')
    m=df.merge(b[['branch_id','opening_year','closing_year']],left_on='primary_branch_id',right_on='branch_id',suffixes=('_cust','_branch'))
    if (m.registration_year<m.opening_year).any() or (m.closing_year_branch.notna()&(m.registration_year>m.closing_year_branch)).any():err.append('branch chronology')
    return sorted(set(err))

def report(df,b):
    ind=df[df.customer_type=='INDIVIDUAL'].copy()
    bus=df[df.customer_type=='BUSINESS'].copy()
    uy=df[df.residence_country=='URUGUAY'].copy()

    print('\n=== DEVELOPMENT REPORT ===')

    # ---------------- Marginal structure ----------------
    for c in ['customer_type','residence_country','customer_status']:
        print(f'\n{c}:\n',df[c].value_counts())
        print('%',df[c].value_counts(normalize=True).mul(100).round(2))

    for c in ['nationality','gender','employment_status']:
        print(f'\n{c}:\n',ind[c].value_counts())
        print('%',ind[c].value_counts(normalize=True).mul(100).round(2))

    # ---------------- Names ----------------
    print('\nTOP FIRST NAMES:\n',ind.first_name.value_counts().head(25))
    print('\nTOP LAST NAMES:\n',ind.last_name.value_counts().head(25))
    print('\nSAMPLE PEOPLE:\n',ind[
        ['customer_id','first_name','last_name','nationality','gender',
         'birth_year','residence_department','residence_locality']
    ].head(20).to_string(index=False))

    # Broad observed birth cohorts for readability.
    ind['birth_cohort']=pd.cut(
        ind.birth_year.astype(int),
        bins=[1900,1959,1979,1999,END_YEAR],
        labels=['<=1959','1960-1979','1980-1999','2000+'],
        include_lowest=True
    )

    print('\nTOP FIRST NAMES BY OBSERVED BIRTH COHORT:')
    for cohort in ind['birth_cohort'].cat.categories:
        x=ind[ind.birth_cohort==cohort].first_name.value_counts().head(15)
        print(f'\n{cohort}:\n{x}')

    # Audit the latent OLD/MIDDLE/YOUNG choice actually made by the generator.
    name_audit=ind[ind._name_cohort!='NEUTRAL'].copy()
    name_audit['birth_band']=pd.cut(
        name_audit.birth_year.astype(int),
        bins=[1900,1955,1965,1975,1985,1995,2000,END_YEAR],
        labels=['<=1955','1956-1965','1966-1975','1976-1985',
                '1986-1995','1996-2000','2001+'],
        include_lowest=True
    )
    cohort_mix=pd.crosstab(
        name_audit.birth_band,
        name_audit._name_cohort,
        normalize='index'
    ).mul(100).round(2)
    print('\nGENERATED NAME-COHORT MIX BY BIRTH BAND (%):\n',cohort_mix)

    # ---------------- Age / employment / income ----------------
    ind['age']=END_YEAR-ind.birth_year.astype(int)
    ind['age_group']=pd.cut(
        ind.age,
        bins=[17,24,34,49,59,69,79,120],
        labels=['18-24','25-34','35-49','50-59','60-69','70-79','80+']
    )

    print('\nAGE DISTRIBUTION:\n',ind.age.describe(
        percentiles=[.01,.05,.10,.25,.50,.75,.90,.95,.99]
    ))
    print('\nAGE GROUP (%):\n',
          ind.age_group.value_counts(normalize=True).sort_index().mul(100).round(2))

    print('\nEMPLOYMENT STATUS x AGE GROUP (% within age group):\n',
          pd.crosstab(ind.age_group,ind.employment_status,normalize='index')
            .mul(100).round(2))

    income_emp=ind.groupby('employment_status',observed=True).monthly_income.agg(
        count='count',mean='mean',median='median',std='std',min='min',max='max'
    ).round(2)
    print('\nMONTHLY INCOME BY EMPLOYMENT STATUS:\n',income_emp)

    income_age=ind.groupby('age_group',observed=True).monthly_income.agg(
        count='count',mean='mean',median='median'
    ).round(2)
    print('\nMONTHLY INCOME BY AGE GROUP:\n',income_age)

    print('\nMONTHLY INCOME OVERALL:\n',
          ind.monthly_income.describe(
              percentiles=[.01,.05,.1,.25,.5,.75,.9,.95,.99]
          ))

    # ---------------- Geography / nationality ----------------
    print('\nRESIDENCE DEPARTMENT:\n',uy.residence_department.value_counts())
    print('\nTOP RESIDENCE LOCALITIES:\n',
          uy.residence_locality.value_counts().head(30))

    nationality_department=pd.crosstab(
        ind.loc[ind.residence_country=='URUGUAY','nationality'],
        ind.loc[ind.residence_country=='URUGUAY','residence_department'],
        normalize='index'
    ).mul(100).round(2)
    print('\nNATIONALITY x RESIDENCE DEPARTMENT (% within nationality):\n',
          nationality_department)

    # Compact geographic diagnostics tied to the designed DGP.
    geo_ind=ind[ind.residence_country=='URUGUAY'].copy()
    diagnostics=[]
    for nat in ['BRAZIL','ARGENTINA','VENEZUELA','CUBA']:
        x=geo_ind[geo_ind.nationality==nat]
        if len(x)==0:
            continue
        if nat=='BRAZIL':
            focus={'Rivera','Cerro Largo','Artigas','Rocha'}
        elif nat=='ARGENTINA':
            focus={'Colonia','Soriano','Río Negro','Paysandú','Salto','Maldonado'}
        else:
            focus={'Montevideo','Canelones','Maldonado'}
        diagnostics.append({
            'nationality':nat,
            'n_uy_residents':len(x),
            'focus_area_share_pct':round(x.residence_department.isin(focus).mean()*100,2),
            'top_department':x.residence_department.value_counts().index[0],
            'top_department_share_pct':round(x.residence_department.value_counts(normalize=True).iloc[0]*100,2)
        })
    print('\nFOREIGN-NATIONALITY GEOGRAPHIC DIAGNOSTICS:\n',
          pd.DataFrame(diagnostics).to_string(index=False))

    # ---------------- Registration / lifecycle ----------------
    print('\nREGISTRATION YEAR:\n',
          df.registration_year.describe(
              percentiles=[.01,.05,.10,.25,.50,.75,.90,.95,.99]
          ))

    df2=df.copy()
    df2['bank_tenure']=END_YEAR-df2.registration_year.astype(int)
    df2['tenure_group']=pd.cut(
        df2.bank_tenure,
        bins=[-1,2,5,10,20,30,40,100],
        labels=['0-2','3-5','6-10','11-20','21-30','31-40','41+']
    )
    status_tenure=pd.crosstab(
        df2.tenure_group,
        df2.customer_status,
        normalize='index'
    ).mul(100).round(2)
    print('\nCUSTOMER STATUS x BANK TENURE (% within tenure group):\n',
          status_tenure)

    # ---------------- Business structure ----------------
    print('\nBUSINESS SECTOR:\n',bus.business_sector.value_counts())
    print('\nCOMPANY SIZE:\n',bus.company_size.value_counts())
    print('\nSAMPLE COMPANIES:\n',bus[
        ['customer_id','company_name','business_sector','company_size',
         'foundation_year','annual_revenue',
         'residence_department','residence_locality']
    ].head(20).to_string(index=False))

    print('\nANNUAL REVENUE OVERALL:\n',
          bus.annual_revenue.describe(
              percentiles=[.01,.05,.1,.25,.5,.75,.9,.95,.99]
          ))

    rev_size=bus.groupby('company_size',observed=True).annual_revenue.agg(
        count='count',mean='mean',median='median',std='std',min='min',max='max'
    ).round(2)
    print('\nANNUAL REVENUE BY COMPANY SIZE:\n',rev_size)

    rev_sector=bus.groupby('business_sector',observed=True).annual_revenue.agg(
        count='count',mean='mean',median='median'
    ).sort_values('median',ascending=False).round(2)
    print('\nANNUAL REVENUE BY BUSINESS SECTOR:\n',rev_sector)

    bus['company_age']=END_YEAR-bus.foundation_year.astype(int)
    age_size=bus.groupby('company_size',observed=True).company_age.agg(
        count='count',mean='mean',median='median',min='min',max='max'
    ).round(2)
    print('\nCOMPANY AGE BY COMPANY SIZE:\n',age_size)

    sector_geo=pd.crosstab(
        bus.loc[bus.residence_country=='URUGUAY','business_sector'],
        bus.loc[bus.residence_country=='URUGUAY','residence_department'],
        normalize='index'
    ).mul(100).round(2)
    print('\nBUSINESS SECTOR x DEPARTMENT (% within sector):\n',sector_geo)

    # ---------------- Branch relationship ----------------
    print('\nCUSTOMERS BY BRANCH:\n',
          df.primary_branch_id.value_counts().sort_index())

    branch_geo=b[['branch_id','department']].rename(
        columns={'department':'branch_department'}
    )
    rel=df.merge(branch_geo,left_on='primary_branch_id',right_on='branch_id',how='left')
    rel_uy=rel[rel.residence_country=='URUGUAY'].copy()
    rel_uy['cross_department']=rel_uy.residence_department!=rel_uy.branch_department

    print('\nCROSS-DEPARTMENT PRIMARY BANKING RELATIONSHIP:')
    print(f"Overall share: {rel_uy.cross_department.mean()*100:.2f}%")
    cross_dep=rel_uy.groupby('residence_department').cross_department.agg(
        customers='count',cross_department_share='mean'
    )
    cross_dep['cross_department_share_pct']=(cross_dep.cross_department_share*100).round(2)
    cross_dep=cross_dep.drop(columns='cross_department_share').sort_values(
        'cross_department_share_pct',ascending=False
    )
    print(cross_dep)

def main():
    df,b=generate()
    print('\nRunning validation...')
    err=validate(df,b)
    if err:
        print('VALIDATION FAILED:',', '.join(err))
        raise RuntimeError('BTYT customer validation failed')

    print('VALIDATION: PASS')

    if DEVELOPMENT_MODE:
        report(df,b)

    # Never export latent audit variables.
    export_df=df.drop(columns=['_name_cohort'],errors='ignore')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    export_df.to_csv(OUT,index=False)

    print(
        f'\nCustomers generated: {len(export_df):,}'
        f'\nColumns: {len(export_df.columns)}'
        f'\nSaved: {OUT}'
    )

if __name__=='__main__':main()
