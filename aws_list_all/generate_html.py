import os
import sys
import webbrowser
from collections import defaultdict
from sys import exit, stderr


def before_content(name):
    origout = sys.stdout
    f = open(name, 'w')
    sys.stdout = f
    print('<!DOCTYPE html>\n<html>\n')
    generate_head()
    print('<body>\n')
    return origout


def after_content(origout):
    print('<script>\n')
    generate_collapsibles()
    generate_searchfunc()
    print('</script>\n')
    print('\n</body>\n')
    print('</html>')
    sys.stdout = origout


def generate_head():
    print('<head>\n')
    print('<style>\n')
    print(""".headerbar {overflow: hidden; background-color: #232F3E; position: fixed; top: 0; width: 100%;}""")
    print(""".headerbar a {float: left; color: #FFFFFF; font-size: 40px; font-family: arial;
        padding: 10px 30px; text-decoration: none;}""")
    print(""".headerbar input[type=text] {margin-top: 12px; margin-right: 30px; border: none; float: right;}""")
    print('.footer {overflow: hidden; background-color: #232F3E; position: fixed; bottom: 0; width: 100%;}')
    print(""".footer a {float: left; color: #f2f2f2; font-size: 12px; font-family: arial;
        padding: 5px 5px; text-decoration: none;}""")
    print('.main {margin-top: 70px; margin-bottom: 30px;}')

    print('.aws-table th {border: none; border-collapse: collapse; border-radius: 10px; background-color: #f1f1f1; '
        + 'font-family: Arial; font-size: 20px; padding: 10px; text-align: center; table-layout:fixed;}\n')
    print('.aws-table td {border: none; border-collapse: collapse; border-radius: 10px; background-color: #f1f1f1; '
        + 'text-align: center; table-layout:fixed;}\n')
    print('.aws-table .service {border: none; border-collapse: collapse; font-family: Arial; '
        + 'font-size: 18px; text-align: center; table-layout:fixed; background-color: #f1f1f1;}\n')
    print('.nfound {border: 10px solid Gold; border-radius: 10px; padding: 10px;}\n')
    print('.found {border: 10px solid LimeGreen; border-radius: 10px; font-size: 20px; padding: 10px;}\n')
    print('.error {border: 10px solid Red; border-radius: 10px; padding: 10px;}\n')
    print('.denied {border: 10px solid DarkOrange; border-radius: 10px; padding: 10px;}\n')
    print('.nCollapse {background-color: Gold; border-radius: 10px; color: white; cursor: pointer; '
        + 'padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}\n')
    print('.fCollapse {background-color: LimeGreen; border-radius: 10px; color: white; cursor: pointer; '
        + 'padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}\n')
    print('.eCollapse {background-color: Red; border-radius: 10px; color: white; cursor: pointer; '
        + 'padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}\n')
    print('.dCollapse {background-color: DarkOrange; border-radius: 10px; color: white; cursor: pointer; '
        + 'padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}\n')
    print('.active, .nCollapse:hover {width: 450px; background-color: #777;}\n')
    print('.active, .fCollapse:hover {width: 450px; background-color: #777;}\n')
    print('.active, .eCollapse:hover {width: 450px; background-color: #777;}\n')
    print('.active, .dCollapse:hover {width: 450px; background-color: #777;}\n')
    print('.content {display: none; overflow: hidden; width: 450px; background-color: #f1f1f1;}\n')

    print(""".popup {position: relative; display: inline-block; cursor: pointer; 
        -webkit-user-select: none; -ms-user-select: none; user-select: none;}\n""")
    print(""".popup .popuptext {visibility: hidden; width: 160px; background-color: #555; color: #fff; 
        text-align: center; border-radius: 6px; padding: 8px 0; position: absolute; z-index: 1; 
        bottom: 125%; left: 50%; margin-left: -80px;}\n""")
    print(""".popup .popuptext::after {content: ""; position: absolute; top: 100%; left: 50%; margin-left: -5px; 
        border-width: 5px; border-style: solid; border-color: #555 transparent transparent transparent;}\n""")
    print('.popup .show {visibility: visible; -webkit-animation: fadeIn 1s; animation: fadeIn 1s;}\n')
    print('@-webkit-keyframes fadeIn {from {opacity: 0;} to {opacity: 1;}}\n')
    print('@keyframes fadeIn {from {opacity: 0;} to {opacity:1 ;}}\n')

    print('#searchInput {\n')
    print('  background-position: 10px 10px;\n')
    print('  background-repeat: no-repeat;\n')
    print('  width: 300px;\n')
    print('  font-size: 16px;\n')
    print('  padding: 12px 20px 12px 40px;\n')
    print('  border: 1px solid #ddd;\n')
    print('  margin-bottom: 12px;\n')
    print('}\n')
    print('</style>\n')
    print('</head>\n')


def generate_header():
    print('<div class="headerbar">')
    print('  <a href="https://github.com/kntrain/aws_list_all"><b>aws_list_all</b></a>')
    print('  <div class="searchbar">')
    print('    <input type="text" id="searchInput" onkeyup="search()" placeholder="FIlter for ...">')
    print('  </div>')
    print('</div>')
    print('<br>')
    #print('<input type="text" id="searchInput" onkeyup="search()" placeholder="Search for ...">')


def generate_table(results_by_region, services_in_grid, id_list):
    id_i = 0
    print('<div class="main">')
    print('<table class="aws-table"; id="mainTable"; table-layout:fixed;>')
    print('    <tr>\n')
    print('        <th>Service</th>\n')
    for region_column in sorted(results_by_region):
        print('<th >' + str(region_column) + '</th>\n')
    print('    </tr>\n')
    rest_by_type = defaultdict(list)
    for service_type in sorted(services_in_grid):
        print('    <tr>\n')
        print('        <td class="service">' + service_type + '</td>\n')
        for result_region in sorted(results_by_region):
            print('        <td width="450">\n')
            for result_type in ('---', '+++', '>:|', '!!!'):
                empty_type = True
                result_type_list = list(filter(lambda x: x[1] == service_type, sorted(results_by_region[result_region][result_type])))
                result_type_count = ' [' + str(len(result_type_list)) + ']'
                for result in result_type_list:
                    if empty_type:
                        print('        <button type="button" class="' + status_switch(result_type + 'col') + '">'
                            + status_switch(result_type + 'box') + result_type_count + '</button>\n')
                        print('        <div class="content">\n')
                        empty_type = False
                    diff_color = ''
                    if len(result) == 7:
                        diff_color = 'style="background-color:' + status_switch(result[6]) + ';"'
                    print('<div class="' + status_switch(result_type) + '" ' + diff_color + '>')
                    print(str(result[3]))
                    print('<br></div>')
                if not(empty_type):
                    print('        </div>')
            print('        </td>')
        print('    </tr>\n')
    print('</table>')
    print('</div>')


def generate_time_footer(start, fin):
    print('<div class="footer">')
    print('  <a>Started processing at: ' + '<span style="color: #98FB98">' + start + '</span>'
        + '; Finished at: ' + '<span style="color: #F08080">' + fin + '</span>' + '</a>')
    print('</div>')


def generate_compare_footer(base, mod):
    print('<div class="footer">')
    print('  <a>Observed changes from: ' + '<span style="color: #98FB98">' + base + '</span>'
        + '   ---->   To: ' + '<span style="color: #F08080">' + mod + '</span>' + '</a>')
    print('</div>')


def generate_collapsibles():
    print('var coll = document.querySelectorAll(".nCollapse,.fCollapse,.eCollapse,.dCollapse");')
    print('var i;\n')
    print('for (i = 0; i < coll.length; i++) {\n')
    print('  coll[i].addEventListener("click", function() {\n')
    print('    this.classList.toggle("active");\n')
    print('    var content = this.nextElementSibling;\n')
    print('    if (content.style.display === "block") {\n')
    print('      content.style.display = "none";\n')
    print('    } else {\n')
    print('      content.style.display = "block";\n')
    print('    }\n')
    print('  });\n')
    print('}\n')


def generate_searchfunc():
    print('function search() {\n')
    print('  var input, filter, table, box, btn, count, el, i, j, btnText, txtValue;\n')
    print('  input = document.getElementById("searchInput");\n')
    print('  filter = input.value.toUpperCase();\n')
    print('  table = document.getElementById("mainTable");\n')
    print("  box = table.querySelectorAll('.content');\n")
    print("  btn = table.querySelectorAll('[type=button]');\n")
    print('  for (i = 0; i < box.length; i++) {\n')

    print("    el = box[i].querySelectorAll('.nfound, .found, .error, .denied');\n")
    print('    count = 0;\n')
    print('    for (j = 0; j < el.length; j++) {\n')
    print('      txtValue = el[j].textContent || el[j].innerText;\n')
    print('      if (txtValue.toUpperCase().indexOf(filter) > -1) {\n')
    print('        el[j].style.display = "";\n')
    print('        count++;\n')
    print('      } else {\n')
    print('        el[j].style.display = "none";\n')
    print('      }\n')
    print('    }\n')
    print('    btnText = btn[i].textContent;\n')
    print('    btn[i].textContent = btnText.substring(0, btnText.indexOf("[") + 1) + count + "]";\n')

    print('  }\n')
    print('}\n')


def generate_popupfunc():
    print('function popup() {\n')
    print('  var popup = document.getElementById("myPopup");\n')
    print('  popup.classList.toggle("show");\n')
    print('}\n')


def status_switch(arg):
    switcher = {
        '---': 'nfound',
        '+++': 'found',
        '!!!': 'error',
        '>:|': 'denied',
        '---box': 'No Resources Found',
        '+++box': 'Resources Found',
        '!!!box': 'Error During Query',
        '>:|box': 'Missing Permissions',
        '---col': 'nCollapse',
        '+++col': 'fCollapse',
        '!!!col': 'eCollapse',
        '>:|col': 'dCollapse',
        'same': '#f1f1f1',
        'added': 'LightGreen',
        'deleted': 'LightCoral'
    }
    return switcher.get(arg, '')