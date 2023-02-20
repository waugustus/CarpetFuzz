opt_ignores = ['"', '.RS']
desc_ignores = ['.IX', '.PD', '.SS', '.RE', '.RS', '.Vb', '.PD', '.UNINDENT', 'INDENT', '.sp', '.']
escape_ch = ['-', '_', '"', ' ', '\\', ".", "'", "´", "`", '.', '\'']
escape_ignore = ['~', '0', '|', '^', '&', ')', '/', ',', ":", "%", "u", "r", "d", "a", "{", "}", '(']

registered_escape_char = ["\"", "#", "*", "$", "'", "`", "-", "_", "%", "!", "?", "s", "~", "0", "|", "^", "&", ")", "/", ",", ":", "n", "{", "}", "(", "[", "a", "A", "b", "B", "c", "C", "d", "D", "e", "E", "f", "F", "g", "h", "H", "k", "l", "L", "m", "M", "n", "N", "o", "O", "p", "r", "R", "s", "S", "t", "u", "v", "V", "w", "x", "X", "Y", "z", "Z"]

special_chars = {
    "Do": "$", "Eu": "€", "Po": "£", "aq": "'", "bu": "•", "co": "©", "cq": "’", "ct": "¢", "dd": "‡", "de": "°", "dg": "†", "dq": "\"", "em": "—", "en": "–", "hy": "‐", "lq": "“", "oq": "‘", "rg": "®", "rq": "”", "rs": "\\", "sc": "§", "tm": "™", "ul": "_", "==": "≡", ">=": "≥", "<=": "≤", "!=": "≠", "->": "→", "<-": "←", "+-": "±"
}

class GroffUtil:
    def __init__(self):
        return

    def parseGroff(self, groff_path):
        prog_name = ''
        opt_desc_dict = {}
        find_option_section = 0
        find_option, find_option_TP = 0, 0
        prev_opt, opt = '', ''

        with open(groff_path, 'r', encoding='utf-8') as f:
            try:
                # Remove some unnecessary tag
                lines = f.read().replace("\\f\\*[B-Font]", "").replace("\\f\\*[I-Font]", "").replace("\\f[]", "").splitlines()
            except:
                print("[ERROR] Failed to read file: %s" % groff_path)
                return -1
        
        i = 0
        while i < len(lines):
            if lines[i].strip() == '':
                pass
            elif lines[i][:3] == '.TH':
                prog_name = lines[i].split(' ')[1]
                if len(prog_name) >= 2 and prog_name[0] == '"' and prog_name[-1] == '"':
                    prog_name = prog_name[1:-1]
            elif lines[i][:3] == '.SH':
                # find OPTION section, skip summary
                if 'option' in lines[i].lower() and 'summary' not in lines[i].lower():
                    find_option_section = 1
                # quit while if OPTION section ends(meet .SH again)
                elif find_option_section == 1:
                    break
            elif find_option_section == 0:
                pass
            
            # Options parsing start
            elif lines[i][:3] in ['.TP', '.PP', '.RS', '.sp']:
                find_option = 1
            elif find_option == 1:
                line = self.__parseLine(lines[i], 'opt')
                line = self.__stripOpt(line)
                if line[:2] == "\\-":
                    line = line[1:]
                if line == '':
                    i += 1
                    continue
                if line[0] == '-':
                    prev_opt = opt
                    opt = line
                    opt_desc_dict[opt] = ''
                elif opt:
                    # print('[WARN] special opt which start with no -, regard as desc and append to opt: %s. The desc is: ' % opt, lines[i])
                    opt_desc_dict[opt] += " %s" % line
                find_option = 0
            elif lines[i][:3] == '.IP':
                find_option = 1
                line_split = lines[i].split('"') 
                if len(line_split) == 1 or line_split[1] == '':
                    i += 1
                    continue
                elif '\\-' not in lines[i].split('.IP')[1] and '"-' not in lines[i].split('.IP')[1] and '-' not in lines[i].split('.IP')[1]: # afraid to just use - instead
                    i += 1
                    continue
                else:
                    line = self.__parseLine(line_split[1], 'opt')
                    if line == '':
                        i += 1
                        continue
                if line[0] == '-':
                    prev_opt = opt
                    opt = line
                    find_option = 0
                    opt_desc_dict[opt] = ''
                elif opt:
                    opt_desc_dict[opt] += ' ' + line
            # elif find_option == 0:
            #     pass
            # Description parsing start
            else:
                desc_line = self.__parseLine(lines[i], 'desc')
                if opt:
                    opt_desc_dict[opt] += ' ' + desc_line
            i += 1

        if find_option_section == 0:
            print("[INFO] No option section found!")
            return 1

        return prog_name.lower(), opt_desc_dict

    def __parseLine(self, raw_line, type):
        raw_line = raw_line.strip()
        # to fix desc after .PP or .TP
        if raw_line[0] not in ['\\', '-', '@']:
            type = 'desc'
        if type == 'opt':
            line_ignores = opt_ignores
        else:
            line_ignores = desc_ignores
        line = ' '

        if raw_line[:3] == '.IP':
            type = 'opt'
            raw_line = raw_line.split('"')[1] if len(raw_line.split('"')) > 1 else ""

        if type == 'desc' and (raw_line[:3] in desc_ignores or raw_line.split(' ')[0] in desc_ignores):
            return line

        i, j = 0, 1
        while i < len(raw_line) - 1:
            # skip keywords start with a dot.
            if raw_line[i] == '.' and raw_line[i+1].isalpha():
                if len(raw_line) <= 3:
                    break
                j = i + 1
                while j < len(raw_line):
                    if raw_line[j] == ' ':
                        i = j - 1
                        break
                    j += 1
            # parse escape sequences
            # refer to https://www.man7.org/linux/man-pages/man7/groff.7.html
            elif raw_line[i] == '\\':
                i += 1
                if raw_line[i] in registered_escape_char:
                    if raw_line[i] =='"' or raw_line[i] =='#':
                        break
                    elif raw_line[i] in escape_ch:
                        line += raw_line[i]
                    elif raw_line[i] == '[':
                        i = i + raw_line[i:].find(']')
                    elif raw_line[i] == 'f' or raw_line[i] == 'F' or raw_line[i] == '*':
                        if raw_line[i+1].isupper():
                            i += 1
                        elif raw_line[i+1] == '(':
                            i += 2
                        elif raw_line[i+1] == '[':
                            i = i + raw_line[i:].find(']')
                        else:
                            # print('[WARN] default i += 1 when dealing with %s' % raw_line[i-1:i+2])
                            i += 1
                    elif raw_line[i] == 's':
                        if raw_line[i+1] == '-':
                            i += 2
                        else:
                            i += 1
                    # \e will be parsed to a back slash
                    elif raw_line[i] == 'e':
                        line += "\\"
                    # special chars
                    elif raw_line[i] == '(':
                        if raw_line[i+1:i+3] in special_chars:
                            line += special_chars[raw_line[i+1:i+3]]
                            i += 2
                    # \x'xxx'
                    elif raw_line[i] in ['h', 'N', 'v', 'x', 'w', 'o', 'R', "b"]:
                        if raw_line[i+1] == "'":
                            i = i + 2 + raw_line[i+2:].find('\'')
                    elif raw_line[i] in ['m', 'g']:
                        if raw_line[i+1] == "(":
                            i += 3
                        elif raw_line[i+1] == "[":
                            i = i + 1 + raw_line[i+1:].find(']')
                        else:
                            i += 1
                    # horizontal tab
                    elif raw_line[i] == "t":
                        line += "   "
                    # line drawing
                    elif raw_line[i] in ['l', 'L']:
                        i += 4
                    # combine with next line
                    elif raw_line[i] == "c":
                        break
                    elif raw_line[i] == "n":
                        # \n
                        if i == len(raw_line) - 1:
                            continue
                        # \n(re
                        elif raw_line[i+1] == "(":
                            i += 2
                        # \n[reg]
                        elif raw_line[i+1] == "[":
                            i += 1 + raw_line[i+1:].find(']')
                        #\nr
                        else:
                            i += 1
                else:
                    line += raw_line[i]
            # skip str in line_ignores, like a quote, but reserver ". "
            elif raw_line[i] in line_ignores and not (raw_line[i] == "." and raw_line[i+1] == " "):
                i += 1
            else:
                line += raw_line[i]
            i += 1

        if i == len(raw_line)-1:
            line += raw_line[-1]
        line = line.strip()

        # Debug information
        # if type == 'opt' and line == '':
        #     print('[WARN] opt is \'\'')
        #     print('[INFO] raw_line == %s'%raw_line)

        return line

    def __stripOpt(self, opt):
        opt = opt.strip("\"").strip()
        if opt == '':
            return ''
        while opt[-1] == ':':
            opt = opt[:-1]
            opt = opt.strip()

        i = 0
        new_opt = ''
        in_bracket = 0
        while i < len(opt):
            if i == 0 and opt[i] == '<':
                in_bracket = 1
            elif in_bracket == 1:
                if opt[i] == '>':
                    in_bracket = 0
                else:
                    new_opt += opt[i]
            else:
                new_opt += opt[i]
            i += 1
        return new_opt