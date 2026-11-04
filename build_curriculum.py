"""Build the versioned, offline interactive curriculum consumed by browser and server."""
import json
from pathlib import Path

EN = [
 ('水果店',[('apple','🍎'),('banana','🍌'),('orange','🍊'),('red','🔴'),('yellow','🟡')],['This is an apple.','The banana is yellow.','This is an orange.','I see red.','I see yellow.'],['Bear sees an apple.','Bear picks a banana.','Bear takes an orange home.'],'🐻 🏪 🍎 🍌 🍊'),
 ('动物朋友',[('cat','🐱'),('dog','🐶'),('rabbit','🐰'),('bird','🐦'),('fish','🐟')],['This is a cat.','I see a dog.','The rabbit is here.','Look at the bird.','The fish is in the water.'],['A cat says hello.','A dog comes to play.','A bird sings goodbye.'],'🏡 🐱 🐶 🐰 🐦 🐟'),
 ('彩色花园',[('red','🔴'),('blue','🔵'),('yellow','🟡'),('green','🟢'),('flower','🌸')],['I see red.','This is blue.','I like yellow.','The leaf is green.','This is a flower.'],['Bear sees a flower.','Bear finds blue.','Bear finds green.'],'🐻 🌸 🔴 🔵 🟡 🟢'),
 ('我的身体',[('hand','✋'),('foot','🦶'),('eye','👁️'),('nose','👃'),('mouth','👄')],['This is my hand.','This is my foot.','Look at my eye.','Touch your nose.','Open your mouth.'],['Bear waves a hand.','Bear touches his nose.','Bear opens his mouth.'],'🐻 ✋ 🦶 👁️ 👃 👄'),
 ('天气小屋',[('sun','☀️'),('moon','🌙'),('cloud','☁️'),('rain','🌧️'),('snow','❄️')],['I see the sun.','The moon is bright.','This is a cloud.','Here comes the rain.','I see snow.'],['Bear sees the sun.','A cloud comes by.','Here comes the rain.'],'🏡 ☀️ 🌙 ☁️ 🌧️ ❄️'),
 ('玩具房',[('ball','⚽'),('car','🚗'),('train','🚂'),('bear','🧸'),('book','📖')],['This is my ball.','I like the car.','Look at the train.','This is my bear.','Open the book.'],['Bear finds a ball.','Bear plays with a car.','Bear opens a book.'],'🏡 ⚽ 🚗 🚂 🧸 📖'),
 ('点心时间',[('milk','🥛'),('bread','🍞'),('egg','🥚'),('water','💧'),('rice','🍚')],['I want some milk.','This is bread.','I see an egg.','I drink water.','I like rice.'],['Bear drinks milk.','Bear eats bread.','Bear drinks water.'],'🐻 🥛 🍞 🥚 💧 🍚'),
 ('出门看看',[('bus','🚌'),('bike','🚲'),('boat','⛵'),('plane','✈️'),('house','🏠')],['Here is a bus.','I see a bike.','Look at the boat.','The plane is up high.','This is my house.'],['Bear leaves the house.','Bear sees a bus.','Bear sees a boat.'],'🐻 🏠 🚌 🚲 ⛵ ✈️'),
 ('小小农场',[('cow','🐮'),('sheep','🐑'),('horse','🐴'),('pig','🐷'),('duck','🦆')],['This is a cow.','I see a sheep.','Look at the horse.','The pig is here.','The duck can swim.'],['Bear meets a cow.','A sheep says hello.','A duck swims by.'],'🌳 🐻 🐮 🐑 🐴 🐷 🦆'),
 ('穿好衣服',[('hat','🧢'),('shirt','👕'),('shoe','👟'),('coat','🧥'),('bag','🎒')],['This is my hat.','I like this shirt.','Here is my shoe.','Put on your coat.','This is my bag.'],['Bear finds his hat.','Bear puts on a coat.','Bear takes his bag.'],'🐻 🧢 👕 👟 🧥 🎒')
]
ZH = [
 ('自然小公园',[('日','☀️'),('月','🌙'),('山','⛰️'),('水','💧'),('木','🌳')],['日光照着大地。','月亮出来了。','山上有树。','小河里有水。','树木长高了。'],['白天有温暖的日光。','小熊走到山脚下。','小熊给树木浇水。'],'🐻 ☀️ 🌙 ⛰️ 💧 🌳'),
 ('身体小伙伴',[('人','🧒'),('口','👄'),('手','✋'),('足','🦶'),('目','👀')],['一个人走过来。','张开小口。','举起小手。','双足站得稳。','目，就是眼睛。'],['一个人来到公园。','他举起手打招呼。','他用目看花朵。'],'🧒 👄 ✋ 🦶 👀 🌸'),
 ('动物来做客',[('牛','🐮'),('羊','🐑'),('马','🐴'),('鸟','🐦'),('鱼','🐟')],['小牛吃青草。','小羊走过来。','小马在草地上。','小鸟在唱歌。','小鱼在水里。'],['小牛来到草地。','小鸟飞过来。','小鱼在水里游。'],'🌳 🐮 🐑 🐴 🐦 🐟'),
 ('数字朋友',[('一','🍎'),('二','🍎🍎'),('三','🍎🍎🍎'),('四','🍎🍎🍎🍎'),('五','🍎🍎🍎🍎🍎')],['一颗苹果放桌上。','两颗苹果，就是二。','三颗苹果排成行。','四颗苹果装进篮。','五颗苹果一起数。'],['小熊拿来一颗苹果。','数字二，是两颗苹果。','三颗苹果送朋友。'],'🐻 🧺 🍎 🍎 🍎'),
 ('比较小世界',[('大','🐘'),('小','🐭'),('多','🍓🍓🍓🍓'),('少','🍓'),('长','🦒')],['大象的身体大。','小老鼠身体小。','这一盘草莓多。','这一盘草莓少。','长颈鹿脖子长。'],['小熊看见大象。','又看见小老鼠。','长颈鹿伸长脖子。'],'🐻 🐘 🐭 🦒 🍓'),
 ('天气观察站',[('天','🌤️'),('云','☁️'),('雨','🌧️'),('风','🍃'),('雪','❄️')],['今天是晴天。','天上有白云。','小雨落下来。','风把叶子吹动了。','雪花轻轻落。'],['白云飘过来。','风吹动了树叶。','小熊听见下雨了。'],'🏠 🌤️ ☁️ 🌧️ 🍃 ❄️'),
 ('我的小书包',[('门','🚪'),('车','🚗'),('书','📖'),('包','🎒'),('衣','👕')],['轻轻打开门。','小车停好了。','翻开一本书。','背上小书包。','穿好上衣。'],['小熊打开门。','他背上书包。','他坐车去看书。'],'🐻 🚪 🚗 📖 🎒 👕'),
 ('方向在哪里',[('上','⬆️'),('下','⬇️'),('中','🎯'),('左','⬅️'),('右','➡️')],['向上看一看。','向下找一找。','靶心在中间。','向左走一步。','向右走一步。'],['小熊向上看。','小熊走到中间。','再向右走一步。'],'🐻 ⬆️ ⬇️ 🎯 ⬅️ ➡️'),
 ('植物小花园',[('花','🌸'),('草','🌱'),('叶','🍃'),('果','🍎'),('米','🍚')],['一朵花开了。','小草绿绿的。','叶子轻轻摇。','树上结了果。','碗里有白米饭。'],['小熊看见花。','又看见绿叶。','他捡到一颗果。'],'🐻 🌸 🌱 🍃 🍎 🍚'),
 ('动作小故事',[('走','🚶'),('跑','🏃'),('坐','🧘'),('立','🧍'),('看','👀')],['慢慢向前走。','小朋友在跑步。','轻轻坐下来。','立，就是站起来。','用眼睛认真看。'],['小熊慢慢走来。','他坐下来休息。','他抬头看天空。'],'🐻 🚶 🏃 🧘 🧍 👀')
]

TRANSFER_PICTURES={'🍎':'🍏','🐱':'🐈','🐶':'🐕','🐰':'🐇','🐦':'🦜','🐟':'🐠','🔴':'🟥','🔵':'🟦','🟡':'🟨','🟢':'🟩','✋':'🖐️','👁️':'👀','☀️':'🌞','🌙':'🌛','🚗':'🚙','🚂':'🚆','🧸':'🐻','🐮':'🐄','🐴':'🐎','🐷':'🐖','⛰️':'🏔️','💧':'🌊','🌳':'🌲','🌸':'🌺'}
ZH_TRANSFER=[
 ['日光暖暖的。','弯弯的月亮挂天上。','远处有一座山。','杯子里有水。','公园里的树木真多。'],
 ['一个人在挥手。','用口说一句你好。','两只手拍拍手。','足球在足边。','双目看着小熊。'],
 ['大牛带着小牛。','羊儿在山坡上。','小马慢慢走。','鸟儿飞上树。','鱼在池塘里游。'],
 ['一颗苹果送给你。','二表示两个。','桌上放着三颗苹果。','四颗苹果分两盘。','五颗苹果数一数。'],
 ['大象比老鼠大。','小老鼠钻进小洞。','这一篮草莓真多。','剩下的草莓少了。','长长的脖子伸过来。'],
 ['天慢慢亮了。','白云变成小船。','雨落在小伞上。','风吹着小风车。','小朋友看着白雪。'],
 ['门外有人来了。','小车带我们出发。','书里藏着故事。','包里放着水杯。','新上衣真漂亮。'],
 ['小鸟向上飞。','树叶落到下面。','小熊站在中间。','左边有一朵花。','右边有一棵树。'],
 ['花园里的花开了。','草地软软的。','小虫停在叶子上。','树上有红红的果。','碗里的米饭香香的。'],
 ['小熊走过花园。','小兔向前跑。','坐在软软的垫子上。','立起来像一棵树。','看一看远处的花。']
]

def phrase(word):
    if word in ['red','yellow','green','blue']:
        return 'something '+word
    if word in ['milk','water','rice','bread','rain','snow']:
        return 'some '+word
    if word in ['sun','moon']:
        return 'the '+word
    return ('an ' if word[0] in 'aeiou' else 'a ')+word

def choices(images, correct, stage, seed):
    unique = list(dict.fromkeys([correct] + images))
    wrong = [x for x in unique if x != correct]
    chosen = [correct] + [wrong[(seed+j) % len(wrong)] for j in range(min(1+int(stage>0),len(wrong)))]
    chosen = list(dict.fromkeys(chosen))
    shift = (seed+1) % len(chosen)
    return chosen[shift:] + chosen[:shift]

def language(kind,index):
    stage=(index-1)%3 if index<=30 else 2
    topic=((index-1)//3 if index<=30 else index-31)%10
    title,words,sentences,story,scene=(EN if kind=='english' else ZH)[topic]
    sentences=list(sentences)
    if stage==2:
        sentences=['I can see '+phrase(word)+'.' for word,_ in words] if kind=='english' else ZH_TRANSFER[topic]
    images=[x[1] for x in words]
    word_images=[TRANSFER_PICTURES.get(p,p) for p in images] if stage==2 else images
    if kind=='chinese' and topic==3 and stage==2:
        word_images=['🍌'*(i+1) for i in range(5)]
    units=[]
    for i,(term,_) in enumerate(words):
        picture=word_images[i]
        q={'id':f'w{i}','kind':'choice','prompt':'换个画面，听一听再找。' if stage==2 else '听一听，找到对应的图片。','speech':term,'lang':'en-US' if kind=='english' else 'zh-CN','display':term,'cue':picture if stage==0 else '', 'options':choices(word_images,picture,stage,i+index),'answer':picture,'hint':f'看看这幅图：{picture}。再听一遍，找一找。'}
        units.append({'id':f'word{i}','label':term,'section':'words','questions':[q]})
    for i,sentence in enumerate(sentences):
        q={'id':f's{i}','kind':'choice','prompt':'听句子，选出对应的画面。','speech':sentence,'lang':'en-US' if kind=='english' else 'zh-CN','display':sentence,'options':choices(images,images[i],stage,i+index+3),'answer':images[i],'hint':f'句子说的是这个画面：{images[i]}。听完再选一次。'}
        units.append({'id':f'sentence{i}','label':sentence,'section':'sentences','questions':[q]})
    story_indices=[0,1,2] if kind=='english' else [[0,2,4],[0,2,4],[0,3,4],[0,1,2],[0,1,4],[1,3,2],[0,3,1],[0,2,4],[0,2,3],[0,2,4]][topic]
    # English theme stories with targets differing from their word-list positions.
    if kind=='english':story_indices=[[0,1,2],[0,1,3],[4,1,3],[0,3,4],[0,2,3],[0,1,4],[0,1,3],[4,0,2],[0,1,4],[0,3,4]][topic]
    if stage==2:
        scene='🌳 🐻 🧺 '+ ' '.join(images)
        if kind=='english':
            story=['Bear is in the park. Bear can see '+phrase(words[story_indices[0]][0])+'.','Can you find '+phrase(words[story_indices[1]][0])+'?','Bear points to '+phrase(words[story_indices[2]][0])+'.']
        else:
            story=[sentences[i] for i in story_indices]
    pages=[]
    for i,line in enumerate(story):
        answer=images[story_indices[i]]
        pages.append({'id':f'p{i}','kind':'story','prompt':'听完这一页，点出故事提到的东西。','speech':line,'lang':'en-US' if kind=='english' else 'zh-CN','display':line,'scene':scene,'options':choices(images,answer,stage,index+i+7),'answer':answer,'hint':f'故事这一页说到了：{answer}。再找一找。'})
    units.append({'id':'story','label':title+'的小故事','section':'story','questions':pages})
    return {'id':f'{kind}-{index}','type':kind,'index':index,'stage':stage,'phase':['认识与体验','辨认与理解','场景应用'][stage] if index<=30 else '巩固复习','theme':title,'units':units}

SKILLS=['观察辨别','分类归纳','规律预测','数量对应','空间几何','顺序关系','逻辑推理','策略规划']
def math(index):
    level=min(2,(index-1)//8)
    units=[]
    for j in range(5):
        skill=(index-1+j)%8
        seed=index+j
        q={'id':f'm{j}','kind':'choice','lang':'zh-CN','ability':SKILLS[skill]}
        if skill==0:
            q.update(prompt='找出和其他图形不一样的那个。',display='●  ●  ▲',speech='这些图形中，哪一个和其他的不一样？',options=choices(['●','▲','■'],'▲',level,seed),answer='▲',hint='两个是圆形，有一个是三角形。找三角形。')
        elif skill==1:
            if level==2:
                q.update(prompt='找一个红色又圆圆的水果。',display='🧺',speech='它是水果，红色的，圆圆的。它是哪一个？',options=choices(['🍎','🍏','🍓'],'🍎',level,seed),answer='🍎',hint='绿色苹果不符合红色的条件，草莓不是圆圆的。试试红苹果。')
            else:
                q.update(prompt='谁能住进水果篮子？',display='🧺 🍎 🍌',speech='篮子里都是水果。谁也可以放进去？',options=choices(['🍊','🚗','🐱'],'🍊',level,seed),answer='🍊',hint='橙子是一种水果，汽车和小猫不是水果。')
        elif skill==2:
            q.update(prompt='接下来应该放什么？',display='🔴 🔵 🔴 🔵 ？' if level<2 else '🔴 🔴 🔵 🔴 🔴 ？',speech='观察颜色的顺序，想一想问号处应该放什么。',options=choices(['🔴','🔵','🟡'],'🔴' if level<2 else '🔵',level,seed),answer='🔴' if level<2 else '🔵',hint='试着把前面的小组再重复一次。')
        elif skill==3:
            n=2+(index%2)+(1 if level==2 else 0)
            q.update(prompt='给每个小熊一个苹果，要选哪一组？',display='🧸 '*n,speech='每个小熊分一个苹果。选出刚刚够的那一组。',options=choices(['🍎'*n,'🍎'*(n-1),'🍎'*(n+1)],'🍎'*n,level,seed),answer='🍎'*n,hint='一个小熊配一个苹果，可以用手指一对一地数。')
        elif skill==4:
            target=1 if level==0 else 3 if level==1 else 5
            direction=['上面','左边','右边'][level]
            q.update(kind='grid',prompt=f'点点小熊{direction}的格子。',speech=f'小熊在中间。点一下它{direction}的格子。',display='小熊在哪里？',grid=['','','','','🐻','','','',''],options=[str(x) for x in range(9) if x!=4],answer=str(target),hint=f'小熊{direction}紧挨着的那一格，就是目标。',highlight=str(target))
        elif skill==5:
            q.update(kind='order',prompt='从小到大，依次点选。',speech='请从最小的圆开始，按从小到大的顺序点选。',display='给圆形排排队',options=['小圆','中圆','大圆'] if level else ['小圆','大圆'],answer=['小圆','中圆','大圆'] if level else ['小圆','大圆'],hint='先点最小的，再点大一点的。',sizes={'小圆':30,'中圆':50,'大圆':70})
            if seed%2:q['options']=q['options'][::-1]
        elif skill==6:
            if level==2:
                q.update(prompt='排除不符合提示的小伙伴。',display='🐰 🐶 🐱',speech='它不是小狗，也没有兔子那样的长耳朵。它是谁？',options=choices(['🐰','🐶','🐱'],'🐱',level,seed),answer='🐱',hint='先排除小狗，再排除长耳朵的兔子，看看还剩谁。')
            else:
                q.update(prompt='根据提示，找到小伙伴。',display='🐰 🐶 🐱',speech='它有长长的耳朵，喜欢吃胡萝卜。它是谁？' if level else '它有长长的耳朵。它是谁？',options=choices(['🐰','🐶','🐱'],'🐰',level,seed),answer='🐰',hint='找长耳朵的兔子。')
        else:
            # A path with only one safe first move. Harder levels add a detour.
            board=['🐻','🌲','','','🌲','','','','🥕'] if level<2 else ['🐻','','🌲','🌲','','🌲','','','🥕']
            target='3' if level<2 else '1'
            q.update(kind='grid',prompt='绕开树，第一步走哪格？',speech='帮助小熊去拿胡萝卜。不能穿过树，也不能跳格。第一步走哪里？',display='给小熊选一条路',grid=board,options=['1','3'],answer=target,hint='先找和小熊相邻、又没有树的格子。',highlight=target)
        units.append({'id':f'challenge{j}','label':SKILLS[skill],'section':'thinking','questions':[q]})
    return {'id':f'math-{index}','type':'math','index':index,'stage':level,'phase':['观察与单步探索','关系与两步思考','迁移与策略应用'][level],'theme':'思维小探险','units':units}

if __name__=='__main__':
    lessons={f'{kind}-{i}':(math(i) if kind=='math' else language(kind,i)) for kind in ['english','chinese','math'] for i in range(1,91)}
    data={'version':1,'subjects':['english','chinese','math'],'skills':SKILLS,'lessons':lessons}
    Path(__file__).with_name('curriculum.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'Built {len(lessons)} lessons; language 5 + 5 + 1, math 5 challenges.')
