import web, os
from web import form, seeother
import sqlalchemy as S
from sqlalchemy.sql import select, delete, and_, func
import datetime


#
# variables
#

web.config.debug = True

class NoUser(dict):
    def __getitem__(me, key):
        return None

class Cals(dict):
    pass

try:
    web.cals
except AttributeError:
    web.cals = Cals()
    web.cals.user = NoUser()

def _noUser():
    return isinstance(web.cals.user, NoUser)
web.cals.noUser = _noUser

engine = S.create_engine('mysql://root:1234@localhost/cals', pool_recycle=3600) 

def connection():
    return engine.connect()

conn = connection()


meta = S.MetaData()
meta.reflect(bind=engine)

for t in meta.tables.keys():
    globals()[t] = meta.tables[t] 

urls = (
    '/', 'netCalories',
    '/day', 'day',
    '/submitActivity', 'submitActivity',
    '/deleteChange', 'deleteChange',
    '/today', 'today',
    '/logout', 'logout',
    '/login', 'login',
    '/doc', 'doc',
    )

def readableDate(str):
    return str

app = web.application(urls, globals(), autoreload=False)

rootdir = os.path.abspath(os.path.dirname(__file__)) + '/'
render = web.template.render(rootdir + 'templates/', globals=globals(), builtins=__builtins__, base='base') 

#
# processors
#

# set user cookie
def loadUser(handler):
    nickname = web.cookies().get('user')
    print nickname, web.cals.user
    if nickname is None:
        web.cals.user = NoUser()
    else:
        if _noUser() or web.cals.user.cnickname != nickname:
            print 'load user'
            user_ = conn.execute(select([tuser], tuser.c.cnickname == nickname)).fetchone()
            if user_ == None:
                web.cals.user = NoUser()
                print 'bad nickname'
            else:
                web.cals.user = user_
                print 'loaded:', web.cals.user
    path = web.ctx.path
    if web.cals.noUser() and not web.ctx.fullpath.startswith('/login'):
        raise seeother('/login')
    else:
        return handler()

def setVars(handler):
    web.cals.latelyClass = "unselected"
    web.cals.todayClass = "unselected"
    web.cals.today = datetime.date.today()
    global conn
    conn = connection()
    return handler()

app.add_processor(setVars)
app.add_processor(loadUser)

application = app.wsgifunc()

#
# actions
#

class today:
    def GET(me):
        raise seeother('/day?date='+str(web.cals.today))

BASE_BURN = 3

class day:
    def GET(me):
        date = web.input().date
        if date == str(web.cals.today):
            web.cals.todayClass = "selected"
        activities = conn.execute(select([tchange, tactivity], 
                                         and_(tchange.c.cdate == date,
                                              tchange.c.cuser == web.cals.user['cid'],
                                              tchange.c.cactivity == tactivity.c.cid),
                                         use_labels=True)
                                  .order_by(tchange.c.cid.asc()))
        found = False
        acs = activities.fetchall()
        for ac in acs:
            if ac.tactivity_cid == BASE_BURN:
                found = True
        if not found:
            conn.execute(tchange.insert().values(cactivity=BASE_BURN,
                                                 camount=web.cals.user['cbaseBurn'],
                                                 cuser=web.cals.user['cid'],
                                                 cdate=date))
            raise seeother('/day?date='+date)
        return render.day(date, acs)

def uniq(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x not in seen and not seen_add(x)]

class netCalories:
    def GET(me):
        week = 1
        if 'week' in web.input():
            week = int(web.input().week)
        ago = web.cals.today - datetime.timedelta(days=7*week)
        days = conn.execute(select([tchange.c.cdate, tactivity.c.ccalories, tchange.c.camount, tchange.c.cactivity],
                                   and_(tchange.c.cdate >= ago, tactivity.c.cid == tchange.c.cactivity))
                            .order_by(tchange.c.cdate.desc())).fetchall()
        web.cals.latelyClass = "selected"
        days = [d for d in days if d['cdate'] != web.cals.today]
        columns = {}
        avg_food = 0.0
        avg_exercise = 0.0
        avg_net = 0.0
        for d in days:
            if d['cdate'] not in columns:
                columns[d['cdate']] = { 'food': 0, 'exercise': 0, 'net': 0}
            dc = columns[d['cdate']]
            if d['ccalories'] > 0:
                tf = d['ccalories'] * d['camount'] 
                dc['food'] += tf
                avg_food += tf
            if d['ccalories'] < 0 and d['cactivity'] != BASE_BURN:
                te = d['ccalories'] * d['camount'] 
                dc['exercise'] += te
                avg_exercise += te
            tn = d['ccalories'] * d['camount']
            dc['net'] += tn
            avg_net += tn

        dates = uniq([d['cdate'] for d in days])
        count = len(dates) if len(dates) > 0 else 1
        return render.netCalories(dates,
                                  columns,
                                  sum([c['net'] for c in columns.values()]),
                                  avg_food=int(round(avg_food / count, 0)),
                                  avg_exercise=int(round(-avg_exercise / count, 0)),
                                  avg_net=int(round(avg_net / count, 0)))

class deleteChange:
    def GET(me):
        conn.execute(delete(tchange, tchange.c.cid == web.input().cid))
        raise seeother(web.input().andthen)        
        
class submitActivity:

    def myform(me):
        rows = conn.execute(tactivity.select())
        today = datetime.date.today()
        return form.Form(
            form.Dropdown(name='activity', args=[row.cname for row in rows]),
            form.Textbox('amount'),
            form.Textbox('date', value=today.strftime("%y/%m/%d")),
            form.Button('submit'),
        )

    def GET(me):
        return render.submit(me.myform(), 'I Just Ate or Exercised')

    def POST(me):
        f = me.myform()
        if not f.validates():
            return render.submit(me.form_, 'I Just Ate or Exercised')
        else:
            activity = conn.execute(select([tactivity], 
                                           tactivity.c.cname == web.input().activity)).fetchone()
            conn.execute(tchange.insert().values(cactivity=activity['cid'],
                                                 camount=web.input().amount,
                                                 cuser=web.cals.user['cid'],
                                                 cdate=web.input().date))
            raise seeother('/day?date='+readableDate(web.input().date))

class login:
    form_ = form.Form(
        form.Textbox('nickname'),
        form.Password('password'),
        form.Button('Login'),
        )

    def GET(me):
        return render.login(me.form_)

    def POST(me):
        f = me.form_()
        if not f.validates():
            return render.login(me.form_)
        else:
            user_ = conn.execute(select([tuser], tuser.c.cnickname == web.input().nickname)).fetchone()
            if user_ is None or user_['cpassword'] != web.input().password:
                return 'bad username or password'
            # set cookie, redirect
            web.setcookie('user', user_['cnickname'])
            raise seeother('/')

class logout:
    def GET(me):
        # delete cookie, redirect
        web.setcookie('user', '', expires=-1)
        raise seeother('/')

class doc:
    def GET(me):
        return getattr(render, web.input().id)()

if __name__ == "__main__":
    app.run()
