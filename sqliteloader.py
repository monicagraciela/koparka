from panda3d.core import *
import sqlite3
import os
from direct.actor.Actor import Actor
from vfx_loader import createEffect

def findAnims(model):
    temp=model.split('_m_')
    path=temp[0]
    anim_name='_a_'+temp[1][:-4]
    name_len=len(anim_name)
    anim_dict={}
    dirList=os.listdir(Filename(path).toOsSpecific())
    for fname in dirList:                        
        if Filename(fname).getExtension() in ('egg', 'bam'): 
            if fname.startswith(anim_name):
                anim_dict[fname[name_len:-4]]=path+fname
    return anim_dict
     
def loadModel(file, collision=None, animation=None):
    model=None
    if animation:
        model=Actor(file, animation)                   
        #default anim
        if 'default' in animation:
            model.loop('default')
        elif 'idle' in animation:
            model.loop('idle')
        else: #some random anim
             model.loop(animation.items()[0])
    else:
        model=loader.loadModel(file)
    model.setPythonTag('model_file', file)
    #load shaders
    for geom in model.findAllMatches('**/+GeomNode'):
        if geom.hasTag('light'):
            model.setPythonTag('hasLight', True)
        if geom.hasTag('particle'):
            file='particle/'+geom.getTag('particle')
            if os.path.exists(file):
                with open(file) as f:  
                    values=json.load(f)
                p=createEffect(values)                
                model.setPythonTag('particle', p)    
                p.start(parent=model, renderParent=render) 
        if geom.hasTag('cg_shader'):            
            geom.setShader(loader.loadShader("shaders/"+geom.getTag('cg_shader')))
        elif geom.hasTag('glsl_shader'):  
            glsl_shader=geom.getTag('glsl_shader')  
            geom.setShader(Shader.load(Shader.SLGLSL, "shaders/{0}_v.glsl".format(glsl_shader),"shaders/{0}_f.glsl".format(glsl_shader)))
        else:
            #geom.setShader(loader.loadShader("shaders/default.cg"))
            geom.setShader(Shader.load(Shader.SLGLSL, "shaders/default_v.glsl","shaders/default_f.glsl"))
    #collisions        
    model.setCollideMask(BitMask32.allOff())
    if collision:
        coll=loader.loadModel(collision)
        coll.reparentTo(model)
        coll.find('**/collision').setCollideMask(BitMask32.bit(2))        
        coll.find('**/collision').setPythonTag('object', model)
        if animation:
            model.setPythonTag('actor_files', [file,animation,coll]) 
    else:
        try:
            model.find('**/collision').setCollideMask(BitMask32.bit(2))        
            model.find('**/collision').setPythonTag('object', model)        
        except:
            print "WARNING: Model {0} has no collision geometry!\nGenerating collision sphere...".format(file)
            bounds=model.getBounds()
            radi=bounds.getRadius()
            cent=bounds.getCenter()
            coll_sphere=model.attachNewNode(CollisionNode('collision'))
            coll_sphere.node().addSolid(CollisionSphere(cent[0],cent[1],cent[2], radi)) 
            coll_sphere.setCollideMask(BitMask32.bit(2))        
            coll_sphere.setPythonTag('object', model)
            #coll_sphere.show()
            if animation:
                model.setPythonTag('actor_files', [file,animation,None])
    return model
    
def LoadScene(file, quad_tree, actors, terrain, textures, current_textures, grass, grass_tex, current_grass_tex, flatten=False):    
    db_name="db/"+file.split('/')[0]+".db"
    map_name=file.split('/')[1]
    connection = sqlite3.connect(db_name)    
            
    with connection:
        connection.row_factory = sqlite3.Row
        cur = connection.cursor()
        #textures
        cur.execute("SELECT tex1, tex2, tex3, tex4, tex5, tex6 FROM textures WHERE map_name=?", (map_name,))
        row = dict(cur.fetchone())
        for tex in row:
            if row[tex] in textures:
                if current_textures:
                    id=textures.index(row[tex])                    
                    current_textures[int(tex[-1])-1]=id
                terrain.setTexture(terrain.findTextureStage(tex), loader.loadTexture(row[tex]), 1)
                normal_tex=row[tex].replace('/diffuse/','/normal/')
                terrain.setTexture(terrain.findTextureStage(tex+'n'), loader.loadTexture(normal_tex), 1)
            else:
                print "WARNING: texture '{0}' not found!".format(row[tex])    
        #grass
        cur.execute("SELECT tex1, tex2, tex3 FROM grass WHERE map_name=?", (map_name,))
        row = dict(cur.fetchone())
        for tex in row: 
            if row[tex] in grass_tex:
                if current_grass_tex:
                    id=grass_tex.index(row[tex])                    
                    current_grass_tex[int(tex[-1])-1]=id                    
                grs_tex=loader.loadTexture(row[tex])
                grs_tex.setWrapU(Texture.WMClamp)
                grs_tex.setWrapV(Texture.WMClamp)
                grass.setTexture(grass.findTextureStage(tex), grs_tex, 1)                    
            else:
                print "WARNING: grass texture '{0}' not found!".format(tex)
        #objects
        cur.execute("SELECT * FROM models WHERE map_name=?", (map_name,))
        objects = cur.fetchall()
        for object in objects:
            model=loadModel(object['model'],object['model'],  )
            model.reparentTo(quad_tree[object['parent_index']]) 
            model.setPythonTag('props', object['props'])
            model.setHpr(render,object['h'],object['p'],object['r'])
            model.setPos(render,object['x'],object['y'],object['z']) 
            model.setScale(object['scale'])
        #actors
        cur.execute("SELECT * FROM actors WHERE map_name=?", (map_name,))
        objects = cur.fetchall()
        for object in objects:
            model=loadModel(object['model'], object['collision'],findAnims(object['model']))
            model.reparentTo(quad_tree[object['parent_index']]) 
            model.setPythonTag('props', object['props'])
            model.setHpr(render,object['h'],object['p'],object['r'])
            model.setPos(render,object['x'],object['y'],object['z']) 
            model.setScale(object['scale'])
            actors.append(model)   
        #lights
        cur.execute("SELECT * FROM lights WHERE map_name=?", (map_name,))
        objects = cur.fetchall()
        for object in objects:
            model=loadModel(object['model'])
            model.reparentTo(quad_tree[object['parent_index']])     
            model.setPos(render,object['x'],object['y'],object['z']) 
            model.setScale(object['scale'])
            model.setPythonTag('light_color', [object['r'],object['g'],object['b']])   
        #'extra_data'
        cur.execute("SELECT * FROM sky WHERE map_name=?", (map_name,))
        sky = dict(cur.fetchone())
        return_data=[{}]
        return_data[0]['SkyTile']=sky['tile']
        return_data[0]['CloudSpeed']=sky['speed']
        cur.execute("SELECT * FROM water WHERE map_name=?", (map_name,))
        water = dict(cur.fetchone())        
        return_data[0]['WaveTile']=water['wave_tile']
        return_data[0]['WaveHeight']=water['wave_height']
        return_data[0]['WaveXYMove']=[water['wave_x'],water['wave_y']]
        return_data[0]['WaterTile']=water['tile']
        return_data[0]['WaterSpeed']=water['speed']
        return_data[0]['WaterLevel']=water['level']
        cur.execute("SELECT * FROM terrain WHERE map_name=?", (map_name,))
        terrain = dict(cur.fetchone())  
        return_data[0]['TerrainTile']=terrain['tile']
        return_data[0]['TerrainScale']=terrain['scale']
        return return_data
        
def SaveScene(file, quad_tree, extra_data=None):        
    db_name="db/"+file.split('/')[0]+".db"
    map_name=file.split('/')[1]
    connection = sqlite3.connect(db_name)
            
    with connection:
        cur = connection.cursor() 
        #create tables if there are none
        cur.execute("CREATE TABLE IF NOT EXISTS models(map_name TEXT, model TEXT, h REAL, p REAL, r REAL, x REAL, y REAL, z REAL, scale REAL, parent_name TEXT, parent_index INTEGER, props TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS actors(map_name TEXT, model TEXT, collision TEXT, h REAL, p REAL, r REAL, x REAL, y REAL, z REAL, scale REAL, parent_name TEXT, parent_index INTEGER, props TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS lights(map_name TEXT, model TEXT, x REAL, y REAL, z REAL, scale REAL, r REAL, g REAL, b REAL, parent TEXT, parent_index INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS textures(map_name TEXT, tex1 TEXT, tex2 TEXT, tex3 TEXT, tex4 TEXT,tex5 TEXT,tex6 TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS sky(map_name TEXT, tile REAL, speed REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS water(map_name TEXT, wave_tile REAL, wave_height REAL, wave_x REAL, wave_y REAL, level REAL, speed REAL, tile REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS terrain(map_name TEXT, tile REAL, scale REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS grass(map_name TEXT, tex1 TEXT, tex2 TEXT, tex3 TEXT)")
        #override (delete) old data
        cur.execute("DELETE FROM models WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM actors WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM lights WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM textures WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM sky WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM water WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM terrain WHERE map_name = ?", (map_name,))
        cur.execute("DELETE FROM grass WHERE map_name = ?", (map_name,))
        if extra_data:
            cur.execute("INSERT INTO sky VALUES(?,?,?)", (map_name, extra_data[0]['SkyTile'],extra_data[0]['CloudSpeed']))
            cur.execute("INSERT INTO water VALUES(?,?,?,?,?,?,?,?)", (map_name, extra_data[0]['WaveTile'],extra_data[0]['WaveHeight'],extra_data[0]['WaveXYMove'][0],extra_data[0]['WaveXYMove'][1],extra_data[0]['WaterLevel'],extra_data[0]['WaterSpeed'],extra_data[0]['WaterTile']))
            cur.execute("INSERT INTO terrain VALUES(?,?,?)", (map_name, extra_data[0]['TerrainTile'],extra_data[0]['TerrainScale']))
            cur.execute("INSERT INTO textures VALUES(?,?,?,?,?,?,?)", (map_name, extra_data[1]['textures'][0], extra_data[1]['textures'][1], extra_data[1]['textures'][2], extra_data[1]['textures'][3], extra_data[1]['textures'][4], extra_data[1]['textures'][5]))
            cur.execute("INSERT INTO grass VALUES(?,?,?,?)", (map_name, extra_data[2]['grass'][0],extra_data[2]['grass'][1],extra_data[2]['grass'][2]))
            
        for node in quad_tree:
            for child in node.getChildren():
                temp={'map_name':map_name}
                if child.hasPythonTag('light_color'):
                    c=child.getPythonTag('light_color')
                    temp['r']=c[0]    
                    temp['g']=c[1]
                    temp['b']=c[2]
                    temp['model']=unicode(child.getPythonTag('model_file'))    
                    temp['x']=child.getX(render)
                    temp['y']=child.getY(render)
                    temp['z']=child.getZ(render)
                    temp['scale']=child.getScale()[0]            
                    temp['parent_name']=node.getName()
                    temp['parent_index']=quad_tree.index(node)
                    cur.execute("INSERT INTO lights VALUES(:map_name, :model, :x, :y, :z, :scale, :r,:g,:b, :parent_name, :parent_index)", temp)                    
                elif child.hasPythonTag('actor_files'):   
                    temp['model']=unicode(child.getPythonTag('actor_files')[0])                    
                    temp['collision']=unicode(child.getPythonTag('actor_files')[2])                       
                    temp['h']=child.getH(render)
                    temp['p']=child.getP(render)
                    temp['r']=child.getR(render)            
                    temp['x']=child.getX(render)
                    temp['y']=child.getY(render)
                    temp['z']=child.getZ(render)
                    temp['scale']=child.getScale()[0]            
                    temp['parent_name']=node.getName()
                    temp['parent_index']=quad_tree.index(node)
                    temp['props']=unicode(child.getPythonTag('props'))
                    cur.execute("INSERT INTO actors VALUES(:map_name, :model, :collision, :h, :p, :r, :x, :y, :z, :scale, :parent_name, :parent_index, :props)", temp)                                     
                elif child.hasPythonTag('model_file'):
                    temp['model']=unicode(child.getPythonTag('model_file'))    
                    temp['h']=child.getH(render)
                    temp['p']=child.getP(render)
                    temp['r']=child.getR(render)            
                    temp['x']=child.getX(render)
                    temp['y']=child.getY(render)
                    temp['z']=child.getZ(render)
                    temp['scale']=child.getScale()[0]            
                    temp['parent_name']=node.getName()
                    temp['parent_index']=quad_tree.index(node)
                    temp['props']=unicode(child.getPythonTag('props'))
                    cur.execute("INSERT INTO models VALUES(:map_name, :model, :h, :p, :r, :x, :y, :z, :scale, :parent_name, :parent_index, :props)", temp)                                     
              
                