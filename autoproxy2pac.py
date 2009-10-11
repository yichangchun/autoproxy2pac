#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
A tool to automatically download autoproxy's GFW list and convert it to a PAC file
So you can bypass GFW's blockade on almost every browser

@version: 0.1
@requires: python 2.6

@author: Meng Xiangliang @ 9#, Tsinghua University
@contact: 911mxl <AT> gmail (e-mail), mengxl (twitter)

@see: AutoProxy add-on for Firefox (https://addons.mozilla.org/en-US/firefox/addon/11009)

@todo:
- Read parameters from command-line
- Generate PAC file using shExpMatch function instead of regular expression, should be faster,
  but it's already fast enough on Safari 4
'''

from __future__ import with_statement
import logging

# Variable names in the PAC file
proxyVar = "PROXY"
defaultVar = "DEFAULT"

# String constants
rulesBegin = "//-- AUTO-GENERATED RULES, DO NOT MODIFY!"
rulesEnd = "//-- END OF AUTO-GENERATED RULES"

defaultPacTemplate = '''/*
 * Proxy Auto-Config file generated by autoproxy2pac
 *  Rule source: %(ruleListUrl)s
 *  Last update: %(ruleListDate)s
 */
function FindProxyForURL(url, host) {
  %(proxyVar)s = "%(proxyString)s";
  %(defaultVar)s = "%(defaultString)s";
%(customCodePre)s
  %(rulesBegin)s
%(ruleListCode)s
  %(rulesEnd)s
%(customCodePost)s
  return %(defaultVar)s;
}
'''

def fetchRuleList(url):
    import urllib, base64
    from contextlib import closing
    with closing(urllib.urlopen(url)) as response:
        list = base64.decodestring(response.read())
        date = response.info().getheader('last-modified')
    return list, date

def rule2js(ruleList):
    import re
    jsCode = []
    
    # The syntax of the list is based on Adblock Plus filter rules (http://adblockplus.org/en/filters)
    #   Filter options (those parts start with "$") is not supported
    # AutoProxy Add-on for Firefox has a Javascript implementation
    #   http://github.com/lovelywcm/autoproxy/blob/master/chrome/content/filterClasses.js
    for line in ruleList.splitlines()[1:]:
        # Ignore the first line ([AutoProxy x.x]), empty lines and comments
        if line and not line.startswith("!"):
            useProxy = True
            
            # Exceptions
            if line.startswith("@@"):
                line = line[2:]
                useProxy = False
            
            # Regular expressions
            if line.startswith("/") and line.endswith("/"):
                jsRegexp = line[1:-1]
            
            # Other cases
            else:
                # Remove multiple wildcards
                jsRegexp = re.sub(r"\*+", r"*", line)
                # Remove anchors following separator placeholder
                jsRegexp = re.sub(r"\^\|$", r"^", jsRegexp, 1)
                # Escape special symbols
                jsRegexp = re.sub(r"(\W)", r"\\\1", jsRegexp)
                # Replace wildcards by .*
                jsRegexp = re.sub(r"\\\*", r".*", jsRegexp)
                # Process separator placeholders
                jsRegexp = re.sub(r"\\\^", r"(?:[^\w\-.%\u0080-\uFFFF]|$)", jsRegexp)
                # Process extended anchor at expression start
                jsRegexp = re.sub(r"^\\\|\\\|", r"^[\w\-]+:\/+(?!\/)(?:[^\/]+\.)?", jsRegexp, 1)
                # Process anchor at expression start
                jsRegexp = re.sub(r"^\\\|", "^", jsRegexp, 1)
                # Process anchor at expression end
                jsRegexp = re.sub(r"\\\|$", "$", jsRegexp, 1)
                # Remove leading wildcards
                jsRegexp = re.sub(r"^(\.\*)", "", jsRegexp, 1)
                # Remove trailing wildcards
                jsRegexp = re.sub(r"(\.\*)$", "", jsRegexp, 1)
                
                if jsRegexp == "":
                    jsRegexp = ".*"
                    logging.warning("There is one rule that matches all URL, which is highly *NOT* recommended: %s", line)
            
            jsLine = "  if(/%s/i.test(url)) return %s;" % (jsRegexp, proxyVar if useProxy else defaultVar)
            if useProxy:
                jsCode.append(jsLine)
            else:
                jsCode.insert(0, jsLine)
    
    return '\n'.join(jsCode)

def parseTemplate(content):
    import re
    template, n = re.subn(r'(?ms)^(\s*?%s\s*?)^.*$(\s*?%s\s*?)$' % (re.escape(rulesBegin), re.escape(rulesEnd)), r'\1%(ruleListCode)s\2', content)
    if n == 0:
        logging.warning("Can not find auto-generated rule section, user-defined rules will LOST during the update")
        return defaultPacTemplate
    
    template = re.sub(r'(Rule source: ).+', r'\1%(ruleListUrl)s', template)
    template = re.sub(r'(Last update: ).+', r'\1%(ruleListDate)s', template)
    return template

def generatePac(rules, configs, template=defaultPacTemplate):
    data = { 'proxyVar'   : proxyVar,
             'defaultVar' : defaultVar,
             'rulesBegin' : rulesBegin,
             'rulesEnd'   : rulesEnd,
             'customCodePre'  : '',
             'customCodePost' : '',
           }
    data.update(configs)
    data.update(rules)
    return template % data

if __name__ == '__main__':
    pacFilepath = "fuckgfw.pac"
    ruleListUrl = "http://autoproxy-gfwlist.googlecode.com/svn/trunk/gfwlist.txt"
    proxyString = "PROXY 127.0.0.1:8118"
    defaultString = "DIRECT"
    
    print("Fetching GFW list from %s ..." % ruleListUrl)
    ruleList, ruleListDate = fetchRuleList(ruleListUrl)
    
    try:
        # Try to update the old PAC file
        with open(pacFilepath) as f:
            template = parseTemplate(f.read())
        print("Updating %s ..." % pacFilepath)
    
    except IOError:
        # Generate new PAC file
        template = defaultPacTemplate
        print("Generating %s ..." % pacFilepath)
    
    rules = { 'ruleListUrl'  : ruleListUrl,
              'ruleListDate' : ruleListDate,
              'ruleListCode' : rule2js(ruleList) }
    configs = { 'proxyString'   : proxyString,
                'defaultString' : defaultString }
    with open(pacFilepath, 'w') as f:
        f.write(generatePac(rules, configs, template))
