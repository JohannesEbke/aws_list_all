import webbrowser
import sys
from collections import defaultdict

DEFINE_HEADERBAR = """
    .headerbar {overflow: hidden; background-color: #232F3E; position: fixed; top: 0; width: 100%;}
    .headerbar a {float: left; color: #FFFFFF; font-size: 40px; font-family: arial;
        padding: 10px 30px; text-decoration: none;}
    .headerbar input[type=text] {margin-top: 12px; margin-right: 30px; border: none; float: right;}\n
"""

DEFINE_FOOTER = """
    .footer {overflow: hidden; background-color: #232F3E; position: fixed; bottom: 0; width: 100%;}
    .footer a {float: left; color: #f2f2f2; font-size: 12px; font-family: arial;
        padding: 5px 5px; text-decoration: none;}\n
"""

DEFINE_TABLE = """
    .aws-table th {border: none; border-collapse: collapse; border-radius: 10px; background-color: #f1f1f1;
        font-family: Arial; font-size: 20px; padding: 10px; text-align: center; table-layout:fixed;}\n
    .aws-table td {border: none; border-collapse: collapse; border-radius: 10px; background-color: #f1f1f1;
        text-align: center; table-layout:fixed;}\n
    .aws-table .service {border: none; border-collapse: collapse; font-family: Arial;
        font-size: 18px; text-align: center; table-layout:fixed; background-color: #f1f1f1;}\n
"""

DEFINE_SEARCHINPUT = """
    #searchInput {
      background-position: 10px 10px;
      background-repeat: no-repeat;
      width: 300px;
      font-size: 16px;
      padding: 12px 20px 12px 40px;
      border: 1px solid #ddd;
      margin-bottom: 12px;
    }
"""
DEFINE_POPUP = """
    .popup {position: relative; display: inline-block; cursor: pointer;
        -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; user-select: none;}\n
    .popup .popuptext {visibility: hidden; width: 160px; background-color: #555; color: #fff;
        text-align: center; border-radius: 6px; padding: 8px 0; position: absolute; z-index: 1;
        bottom: 125%; left: 50%; margin-left: -80px;}\n
    .popup .popuptext::after {content: ""; position: absolute; top: 100%; left: 50%; margin-left: -5px;
        border-width: 5px; border-style: solid; border-color: #555 transparent transparent transparent;}\n
    .popup .show {visibility: visible; -webkit-animation: fadeIn 1s; animation: fadeIn 1s;}\n
    @-webkit-keyframes fadeIn {from {opacity: 0;} to {opacity: 1;}}\n
    @keyframes fadeIn {from {opacity: 0;} to {opacity:1 ;}}\n
"""


def html_doc_start():
    """Return a string containing the beginning and head of appropriate html-file"""
    return ('<!DOCTYPE html>\n' + '<html>\n' + generate_head() + '<body>\n')


def generate_file(orig_dir, name, content):
    """Finish writing the HTML-content, create respective file and open it in a browser"""
    lines = []
    lines.append(content)
    lines.append('<script>\n')
    lines.append(generate_collapsibles())
    lines.append(generate_searchfunc())
    lines.append(generate_popupfunc())
    lines.append('</script>\n')
    lines.append('\n</body>\n')
    lines.append('</html>')

    origout = sys.stdout
    url = orig_dir + '/' + name + '.html'
    f = open(url, 'w')
    sys.stdout = f
    print(''.join(lines))
    sys.stdout = origout
    webbrowser.open(url, new=2)


def generate_head():
    html_head = []
    html_head.append('<head>\n')
    html_head.append('<style>\n')

    html_head.append(DEFINE_HEADERBAR)
    html_head.append(DEFINE_FOOTER)
    html_head.append('.main {margin-top: 70px; margin-bottom: 30px;}\n')
    html_head.append(DEFINE_TABLE)

    html_head.append(
        """
        .nfound {border: 10px solid Gold; border-radius: 10px; padding: 10px;}
        .found {border: 10px solid LimeGreen; border-radius: 10px; padding: 10px;}
        .error {border: 10px solid Red; border-radius: 10px; padding: 10px;}
        .denied {border: 10px solid DarkOrange; border-radius: 10px; padding: 10px;}
        .nCollapse {background-color: Gold; border-radius: 10px; color: white; cursor: pointer;
            padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}
        .fCollapse {background-color: LimeGreen; border-radius: 10px; color: white; cursor: pointer;
            padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}
        .eCollapse {background-color: Red; border-radius: 10px; color: white; cursor: pointer;
            padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}
        .dCollapse {background-color: DarkOrange; border-radius: 10px; color: white; cursor: pointer;
            padding: 14px; width: 450px; border: none; text-align: center; font-size: 20px;}
        .active, .nCollapse:hover {width: 450px; background-color: #777;}
        .active, .fCollapse:hover {width: 450px; background-color: #777;}
        .active, .eCollapse:hover {width: 450px; background-color: #777;}
        .active, .dCollapse:hover {width: 450px; background-color: #777;}
        .content {display: none; overflow: hidden; width: 450px; background-color: #f1f1f1;}
    """
    )
    html_head.append(DEFINE_POPUP)
    html_head.append(DEFINE_SEARCHINPUT)
    html_head.append('</style>\n')
    html_head.append('</head>\n')

    return ''.join(html_head)


def generate_header():
    return """
        <div class="headerbar">
          <a href="https://github.com/kntrain/aws_list_all"><b>aws_list_all</b></a>
          <div class="searchbar">
            <input type="text" id="searchInput" onkeyup="search()" placeholder="FIlter for ...">
          </div>
        </div>
        <br>\n
    """


def generate_table(results_by_region, services_in_grid):
    html_table = []
    html_table.append(
        """
        <div class="main">
        <table class="aws-table"; id="mainTable"; table-layout:fixed;>
            <tr>
                <th>Service</th>\n"""
    )
    for region_column in sorted(results_by_region):
        html_table.append('<th >' + str(region_column) + '</th>\n')
    html_table.append('    </tr>\n')

    for service_type in sorted(services_in_grid):
        html_table.append('    <tr>\n')
        html_table.append('        <td class="service">' + service_type + '</td>\n')
        for result_region in sorted(results_by_region):
            html_table.append('        <td width="450">\n')
            for result_type in ('---', '+++', '>:|', '!!!'):
                empty_type = True
                result_type_list = list(
                    filter(
                        lambda x: x.input.service == service_type,
                        sorted(results_by_region[result_region][result_type])
                    )
                )
                result_type_count = ' [' + str(len(result_type_list)) + ']'
                diffs_count = diff_count(result_type_list)
                for result in result_type_list:
                    if empty_type:
                        html_table.append(
                            '        <button type="button" class="' + status_switch(result_type + 'col') + '">' +
                            status_switch(result_type + 'box') + result_type_count + diffs_count + '</button>\n'
                        )
                        html_table.append('        <div class="content">\n')
                        empty_type = False
                    diff_color = ''
                    if result.diff:
                        diff_color = 'style="background-color:' + status_switch(result.diff) + ';"'
                    html_table.append('<div class="' + status_switch(result_type) + '" ' + diff_color + '>')
                    html_table.append(str(result.input.operation))
                    if result_type == '+++':
                        html_table.append('<p style="font-size:14px;margin:0">')
                        html_table.append(str(result.id_list))
                        html_table.append('</p>')
                    html_table.append('</div>')
                if not (empty_type):
                    html_table.append('        </div>\n')
            html_table.append('        </td>')
        html_table.append('    </tr>\n')
    html_table.append('</table>\n')
    html_table.append('</div>\n')

    return ''.join(html_table)


def generate_time_footer(start, fin):
    return (
        '<div class="footer">\n' + '  <a>Started processing at: ' + '<span style="color: #98FB98">' + start +
        '</span>' + '; Finished at: ' + '<span style="color: #F08080">' + fin + '</span>' + '</a>\n' + '</div>\n'
    )


def generate_compare_footer(base, mod):
    return (
        '<div class="footer">\n' + '  <a>Observed changes from: ' + '<span style="color: #98FB98">' + base + '</span>' +
        '   ---->   To: ' + '<span style="color: #F08080">' + mod + '</span>' + '</a>\n' + '</div>\n'
    )


def generate_collapsibles():
    return """
        var coll = document.querySelectorAll(".nCollapse,.fCollapse,.eCollapse,.dCollapse");\n
        var i;\n
        for (i = 0; i < coll.length; i++) {\n
          coll[i].addEventListener("click", function() {\n
            this.classList.toggle("active");\n
            var content = this.nextElementSibling;\n
            if (content.style.display === "block") {\n
              content.style.display = "none";\n
            } else {\n
              content.style.display = "block";\n
            }\n
          });\n
        }\n
    """


def generate_searchfunc():
    return """
        function search() {\n
          var input, filter, table, box, btn, count, el, i, j, btnText, txtValue;\n
          input = document.getElementById("searchInput");\n
          filter = input.value.toUpperCase();\n
          table = document.getElementById("mainTable");\n
          box = table.querySelectorAll('.content');\n
          btn = table.querySelectorAll('[type=button]');\n
          for (i = 0; i < box.length; i++) {\n
            el = box[i].querySelectorAll('.nfound, .found, .error, .denied');\n
            count = 0;\n
            for (j = 0; j < el.length; j++) {\n
              txtValue = el[j].textContent || el[j].innerText;\n
              if (txtValue.toUpperCase().indexOf(filter) > -1) {\n
                el[j].style.display = "";\n
                count++;\n
              } else {\n
                el[j].style.display = "none";\n
              }\n
            }\n
            btnText = btn[i].textContent;\n
            btn[i].textContent = btnText.substring(0, btnText.indexOf("[") + 1) + count + "]";\n
          }\n
        }\n
    """


def generate_popupfunc():
    return """
        function popup() {\n
          var popup = document.getElementById("myPopup");\n
          popup.classList.toggle("show");\n
        }\n
    """


def wrap_popup(result_type, text, id_list):
    if not result_type == '+++':
        return text
    else:
        return (
            '<div class="popup" onclick="popup()">' + text + '\n' + '  <span class="popuptext" id="myPopup">' +
            str(id_list) + '</span>\n' + '</div>\n'
        )


def diff_count(result_list):
    count_str = '-'
    counts = defaultdict(int)
    if not result_list or result_list[0].diff == '':
        return ''
    for result in result_list:
        counts[result.diff] += 1
    counts.pop('same', None)
    for count in counts:
        count_str += str(counts[count]) + ' ' + count[:3] + '-'
    return ' [' + count_str + ']'


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
