import numpy as np
import sys
import os
import random
from collections import defaultdict

from bottle import route, run, response, abort, static_file, request, redirect
import mimetypes, base64

from decorators import gzipped, session_logged
from index import Index

if len(sys.argv) < 2:
    print('usage: %s <index-directory+>' % sys.argv[0])
    sys.exit(1)

indexes = {}
default_index = None
for directory in sys.argv[1:]:
    name = directory.split('/')[-1]
    if default_index is None:
        default_index = name
    indexes[name] = Index(directory)

def closest(db, target, n):
    return db.closest(target, n)

def closest_diverse(db, target, n, random_ratio = .4, mmr_redundancy = .95):
    np.random.seed(target)
    split = int(n * random_ratio)
    #selected = np.random.randint(0, db.vectors.shape[0], n * 2)
    selected = np.random.choice(range(db.vectors.shape[0]), n * 3, replace=False)
    scores = np.dot(db.vectors[selected], db.vectors[target].T)
    result = list(db.closest(target, n - split)) + [(scores[i], selected[i]) for i in range(len(selected))]
    filtered_for_doubles = []
    seen_images = set()
    for score, i in result:
        if i not in seen_images:
            filtered_for_doubles.append((score, i))
            seen_images.add(i)

    sorted_results = sorted(filtered_for_doubles, key=lambda x: -x[0])

    selected = np.zeros((n, db.vectors.shape[1]))
    selected[0] = db.vectors[target]
    selected_ids = [target]
    v = db.vectors[sorted_results[0][1]]
    j = 0
    for i in range(1, n):
        value = 1
        while j < len(sorted_results) - 1 and value > mmr_redundancy:
            j += 1
            v = db.vectors[sorted_results[j][1]]
            value = max(np.dot(selected[:len(selected_ids)], v.T))
            #print(i, j, value)
        if j == len(sorted_results) - 1:
            break
        selected[i] = v
        selected_ids.append(j)
    if len(selected_ids) < len(sorted_results):
        selected_ids = range(len(sorted_results))[:n]
    return [(1, target)] + [sorted_results[j] for j in selected_ids[1:]]

#########################

@route('/static/<path:path>')
def callback(path):
    return static_file(path, root='./static/')

def template(body):
    with open('static/style.css') as fp:
        css = fp.read()
    return '''<DOCTYPE html>
    <html>
        <head>
             <style>''' + css + '''</style>
        </head>
        <body>
            <div style="position:fixed; left:0px; bottom:0px; font-size: 300%">
                <a href="javascript:history.back()">🡄</a>
                <a href="javascript:history.forward()">🡆</a>
                <a href="/">🏠</a>
            </div>
        ''' + body + '''</body>
    </html>'''

def get_image_url(index, num, use_data_url=False):
    if index not in indexes:
        print('index "%s" not found' % index)
        return ''
    db = indexes[index]
    name = db.image(num)
    mime = mimetypes.guess_type(name)
    if mime[0] is not None:
        if use_data_url:
            try:
                encoded = base64.b64encode(open(name, 'rb').read())
                return 'data:%s;base64,%s' % (mime[0], encoded.decode())
            except:
                print('not found', name)
                return ''
        else:
            return '/image/%s/%d' % (index, num)
    return ''

@route('/image/<index>/<num:int>')
def image(index, num):
    if index not in indexes:
        abort(404, 'index "%s" not found' % index)
    db = indexes[index]
    name = db.image(num)
    mime = mimetypes.guess_type(name)
    if mime[0] is not None:
        return static_file(name.split('/')[-1], root=db.image_directory, mimetype=mime[0])
    abort(404, 'image %d not found' % num)

@gzipped()
@route('/1d-sorted/<index>/m=<method>/t=<target:int>/n=<num:int>/r=<redundancy:float>')
@session_logged()
def sorted_1d(index, method='diverse', target=0, num=109, redundancy=.95):
    if index not in indexes:
        abort(404, 'index "%s" not found' % index)
    db = indexes[index]
    if db.image(target) is None:
        abort(404, 'not found')
    if method == 'diverse':
        found = closest_diverse(db, target, num, mmr_redundancy=redundancy)
    elif method == 'closest':
        found = db.closest(target, num)
    else:
        abort(501, 'method not supported')
    content = ''
    for score, i in found:
        description = db.description(i)
        if i == target:
            content += '<img style="float:left" title="%s" alt="%s" width="224" height="224" src="%s">' % (description, description, get_image_url(index, i))
        else:
            content += '<a href="/1d-sorted/%s/m=%s/t=%d/n=%d/r=%g"><img title="%s" alt="%s" width="112" height="112" src="%s"></a>' % (index, method, i, num, redundancy, description, description, get_image_url(index, i))
    #response.set_header("Cache-Control", "public, max-age=604800")
    return template(content)

@gzipped()
@route('/2d-sorted/<index>/m=<method>/t=<target:int>/w=<N:int>/h=<M:int>/r=<random_ratio:float>/t=<redundancy_threshold:float>')
@session_logged()
def sorted_2d(index, method='diverse', target=0, N=12, M=8, random_ratio=.1, redundancy_threshold=.75):
    if index not in indexes:
        abort(404, 'index "%s" not found' % index)
    db = indexes[index]
    if db.image(target) is None:
        abort(404, 'not found')
    import grid_sort
    NUM = N * M
    if method  == 'diverse':
        found = np.array([x[1] for x in closest_diverse(db, target, NUM - 3, random_ratio=random_ratio, mmr_redundancy=redundancy_threshold)])
    elif method == 'closest':
        found = np.array([x[1] for x in db.closest(target, NUM - 3)])
    else:
        abort(501, 'method not supported')

    vectors = db.vectors[found]

    indices = np.arange(NUM).reshape(N, M)
    fixed = np.zeros((N, M))

    CN, CM = N // 2 - 1, M // 2 - 1

    indices[N - 1, M - 1] = indices[CN, CM]
    indices[N - 1, M - 2] = indices[CN + 1, CM]
    indices[N - 1, M - 3] = indices[CN, CM + 1]
    indices[0, 0] = indices[CN + 1, CM + 1]

    indices[CN, CM] = 0
    indices[CN + 1, CM] = 0
    indices[CN, CM + 1] = 0
    indices[CN + 1, CM + 1] = 0

    fixed[CN, CM] = 1
    fixed[CN + 1, CM] = 1
    fixed[CN, CM + 1] = 1
    fixed[CN + 1, CM + 1] = 1

    grid_sort.seed(target)
    indices = grid_sort.sort(vectors, N, M, indices, fixed)

    table = '<table border="0" cellspacing="0" cellpadding="0" style="margin: auto">'
    for j in range(M):
        row = '<tr>'
        for i in range(N):
            image = found[indices[i, j]]
            description = db.description(image)
            if i == CN and j == CM:
                row += '<td colspan="2" rowspan="2" style="text-align: center"><img title="%s" alt="%s" src="%s" width="210" height="210"></td>' % (description, description, get_image_url(index, image))
            elif i == CN + 1 and j == CM:
                pass
            elif i == CN and j == CM + 1:
                pass
            elif i == CN + 1 and j == CM + 1:
                pass
            else:
                row += '<td><a href="/2d-sorted/%s/m=%s/t=%d/w=%d/h=%d/r=%g/t=%g"><img title="%s" alt="%s" src="%s" width="112" height="112"></a></td>' % (index, method, image, N, M, random_ratio, redundancy_threshold, description, description, get_image_url(index, image))
        row += '</tr>'
        table += row
    table += '</table>'
    return template(table) 

@route('/starting-point/<index>/w=<width:int>/h=<height:int>')
@session_logged()
def starting_point(index, width=14, height=8):
    if index not in indexes:
        abort(404, 'index "%s" not found' % index)
    db = indexes[index]

    random.seed(hash(request.query.parameters))
    indices = random.sample(range(0, len(db.images)), width * height)

    parameters = request.query.parameters
    parameters = parameters.replace('$INDEX', index).replace('$WIDTH', str(width)).replace('$HEIGHT', str(height))

    table = '<table border="0" cellspacing="0" cellpadding="0" style="margin: auto">'
    for j in range(height):
        row = '<tr>'
        for i in range(width):
            image = indices[j * width + i]
            description = db.description(image)
            row += '<td><a href="%s"><img title="%s" alt="%s" src="%s" width="112" height="112"></a></td>' % (parameters.replace('$TARGET', str(image)), description, description, get_image_url(index, image))
        row += '</tr>'
        table += row
    table += '</table>'
    return template(table)

@route('/')
@session_logged()
def index():
    body = ''
    for name in indexes:
        body += '<h1>%s</h1>' % name
        body += '<ul>'
        body += '<li><a href="/starting-point/%s/w=14/h=8?parameters=/2d-sorted/$INDEX/m=diverse/t=$TARGET/w=$WIDTH/h=$HEIGHT/r=.5/t=.85">Diverse, 2d-sorted</a></li>' % (name)
        body += '<li><a href="/starting-point/%s/w=14/h=8?parameters=/2d-sorted/$INDEX/m=closest/t=$TARGET/w=$WIDTH/h=$HEIGHT/r=.5/t=.85">Closest, 2d-sorted</a></li>' % (name)
        body += '<li><a href="/starting-point/%s/w=14/h=8?parameters=/1d-sorted/$INDEX/m=diverse/t=$TARGET/n=115/r=.95">Diverse, 1d-sorted</a></li>' % (name)
        body += '<li><a href="/starting-point/%s/w=14/h=8?parameters=/1d-sorted/$INDEX/m=closest/t=$TARGET/n=115/r=.95">Closest, 1d-sorted</a></li>' % (name)
        body += '</ul>'

    return template(body)

if __name__ == '__main__':
    run(server='bjoern', host='localhost', port=8080)

