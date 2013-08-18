#! /usr/bin/env python

import re, sys
from psfile import PSFile
from types import ListType, StringType

class Sheet (object):
  def __init__ (self, conf, sheet, page, fname):
    self.re_var = re.compile (r"^\$\{([A-Za-z0-9._]+)\}$")
    self.conf = conf
    self.fname = fname
    self.fd = None
    # Type of sheet
    self.sheet = sheet
    self.page = page
    self.rotate = self.value ("rotate")
    # Size of grid
    self.num_x = int (self.value ("num_across_x"))
    self.num_y = int (self.value ("num_across_y"))
    # Size of tile
    self.tile_x = int (self.value ("tile_x"))
    self.tile_y = int (self.value ("tile_y"))
    # Size of rubber frame
    self.rubber_x = int (self.value ("rubber_x"))
    self.rubber_y = int (self.value ("rubber_y"))
    # Offsets for inner tile block
    self.x_off = (self.rubber_x - (self.tile_x * self.num_x)) / 2
    self.y_off = (self.rubber_y - (self.tile_y * self.num_y)) / 2

  def __enter__ (self):
    return self

  def __exit__ (self, t, v, tr):
    pass

  def open (self):
    self.fd = PSFile (self.fname, paper = self.value ("paper"),
                      margin = 36)
    if self.rotate == "1":
      self.fd.append ("270 rotate")
      self.fd.append ("-%d %d translate" % (self.fd.height, 0))

  def close (self):
    if self.fd:
      self.fd.close ()
      self.fd = None

  def _get_value (self, sl, k):
    base = self.conf
    al = list ()
    # Descending list of sections
    for s in sl:
      a = base.get (s)
      if not a:
        break
      al.insert (0, a)
      base = a
    al.append (self.conf.get ("DEFAULT"))
    for d in al:
      # print "K: ", k , "D: ", d, "V: [%s]" % d.get (k)
      if d.has_key (k):
        return d.get (k)
    raise ValueError

  def value (self, n, x = 0, y = 0):
    sl = [self.sheet, self.page, "tile_%d%d" % (x + 1, y + 1)]
    try:
      v = self._get_value (sl, n)
    except:
      print >> sys.stderr, (
        "FAULT: No definition found for: %s.%s.%s (%d, %d)"
        % (self.sheet, self.page, n, x + 1, y + 1))
      sys.exit (1)
    if v == "randomcolour": # Development ease
      from random import uniform
      v = (uniform (0, 1), uniform (0, 1), uniform (0, 1))
    elif isinstance (v, ListType): # So it satisfies the % operator
      v = tuple (v)
    else: # Substitute ${VAR} value
      m = self.re_var.search (v)
      if m:
        k = m.group (1) # Variable name
        v = self.value (k, x, y) # Replacement token
    return v

  def page_align (self):
    align_length = float (self.value ("align_length"))
    self.fd.append ("gsave")
    for i in [((self.rubber_x / 2.0, 0), (0, 0 - align_length)),
              ((self.rubber_x /2.0, self.rubber_y), (0, align_length)),
              ((0, self.rubber_y / 2.0), (0 - align_length, 0)),
              ((self.rubber_x, self.rubber_y / 2.0), (align_length, 0)),]:
      self.line ("align", i[0][0], i[0][1], i[1][0], i[1][1])
    self.fd.append ("grestore")

  def page_frame (self):
    self.box ("frame", 0, 0, self.rubber_x, self.rubber_y)

  def push_tile (self, x, y):
    self.fd.append ("gsave")
    self.fd.append ("%d %d translate" % (x, y))
    if self.value ("outline", x, y) == "1":
      self.box ("tile", 0, 0, self.tile_x, self.tile_y)
    self.fd.append ("newpath")

  def pop_tile (self):
    self.fd.append ("grestore")

  def line (self, typ, x, y, w, h):
    stroke_width = float (self.value ("%s_stroke" % typ))
    colour = self.value ("%s_colour" % typ)
    self.fd.append ("gsave")
    self.fd.append ("%s %s %s setrgbcolor" % colour)
    self.fd.append ("%f setlinewidth" % stroke_width)
    self.fd.append ("%f %f moveto" % (x, y))
    self.fd.append ("%f %f lineto" % (x + w, y + h))
    self.fd.append ("stroke")
    self.fd.append ("grestore")

  def box (self, typ, x, y, w, h):
    stroke = float (self.value ("%s_stroke" % typ))
    stroke_colour = self.value ("%s_stroke_colour" % typ)
    colour_bg = self.value ("%s_colour" % typ)
    self.fd.append ("gsave")
    if colour_bg != "transparent":
      self.fd.append ("%s %s %s setrgbcolor" % colour_bg)
      self.fd.append ("%f %f %f %f rectfill" % (x, y, w, h))
    if stroke_colour != "transparent":
      self.fd.append ("%s %s %s setrgbcolor" % stroke_colour)
      self.fd.append ("%f setlinewidth" % stroke)
      self.fd.append ("%f %f %f %f rectstroke" % (x, y, w, h))
    self.fd.append ("grestore")

  def text (self, typ, x, y, h_centre = -1, v_centre = 1):
    line_height = float (self.value ("%s_line_height" % typ))
    self.fd.append ("gsave")
    self.fd.append ("currentpoint translate")
    self.fd.append ("/%s %s selectfont" % self.value ("%s_font" % typ, x, y))
    self.fd.append ("%s %s %s setrgbcolor"
                    % self.value ("%s_colour" % typ, x, y))
    tl = self.value (typ, x, y)
    if isinstance (tl, StringType):
      tl = tl.split ("\n")
    if v_centre == 1:
      by = 0
    if v_centre == 0:
      by = line_height * ((float (len (tl) - 1) / 2))
      self.fd.append ("0 %d moveto" % by)
    if v_centre == -1:
      by = line_height * (len (tl) - 1)
      self.fd.append ("0 %d moveto" % by)
    format = {
      -1: "(%s) show",
      0: "(%s) dup stringwidth pop 2 div neg 0 rmoveto show",
      1: "(%s) dup stringwidth pop neg 0 rmoveto show",
      }
    for t in tl:
      self.fd.append (format[h_centre] % t)
      by -= line_height
      self.fd.append ("0 %d moveto" % by)
    self.fd.append ("grestore")

  def company_token_circle (self, x, y):
    token_radius = float (self.value ("token_radius", x, y))
    colour = self.value ("token_colour", x, y)
    stroke = float (self.value ("token_stroke", x, y))
    stroke_colour = self.value ("token_stroke_colour", x, y)
    self.fd.append ("gsave")
    self.fd.append ("currentpoint translate")
    self.fd.append ("newpath")
    self.fd.append ("0 0 %f 0 360 arc" % token_radius)
    self.fd.append ("gsave")
    self.fd.append ("%s %s %s setrgbcolor" % colour)
    self.fd.append ("fill")
    self.fd.append ("grestore")
    self.fd.append ("%s %s %s setrgbcolor" % stroke_colour)
    self.fd.append ("%f setlinewidth" % stroke)
    self.fd.append ("stroke")
    self.fd.append ("grestore")

  def company_token (self, x, y):
    stroke = float (self.value ("token_stroke", x, y))
    stroke_colour = self.value ("token_stroke_colour", x, y)
    radius = float (self.value ("token_radius", x, y))
    stripe_angle = float (self.value ("token_stripe_angle", x, y))
    stripe_text_fudge = float (self.value ("token_stripe_text_fudge", x, y))
    self.company_token_circle (x, y)
    # Setup
    self.fd.append ("gsave")
    self.fd.append ("currentpoint translate")
    self.fd.append ("newpath")
    # Token top
    self.fd.append ("gsave")
    self.fd.append ("0 0 %f %f %f arc"
                    % (radius, 0 + stripe_angle, 180 - stripe_angle))
    self.fd.append ("closepath")
    self.fd.append ("gsave")
    self.fd.append ("%s %s %s setrgbcolor"
                    % self.value ("token_top_colour", x, y))
    self.fd.append ("fill")
    self.fd.append ("grestore")
    self.fd.append ("%s %s %s setrgbcolor" % stroke_colour)
    self.fd.append ("%f setlinewidth" % stroke)
    self.fd.append ("stroke")
    self.fd.append ("grestore")
    # Token bottom
    self.fd.append ("gsave")
    self.fd.append ("0 0 %f %f %f arc"
                    % (radius, 180 + stripe_angle, 0 - stripe_angle))
    self.fd.append ("closepath")
    self.fd.append ("gsave")
    self.fd.append ("%s %s %s setrgbcolor"
                    % self.value ("token_top_colour", x, y))
    self.fd.append ("fill")
    self.fd.append ("grestore")
    self.fd.append ("%s %s %s setrgbcolor" % stroke_colour)
    self.fd.append ("%f setlinewidth" % stroke)
    self.fd.append ("stroke")
    self.fd.append ("grestore")
    # Token text
    self.fd.append ("gsave")
    self.fd.append ("0 %f moveto" % (0 - stripe_text_fudge))
    self.text ("token_name", x, y, h_centre = 0, v_centre = 0)
    self.fd.append ("grestore")
    # Done
    self.fd.append ("grestore")

  def make (self):
    self.open ()
    self.page_align ()
    self.page_frame ()
    self.page_details ()
    ox = self.x_off
    oy = self.y_off
    for x in xrange (self.num_x):
      for y in xrange (self.num_y):
        bx = (x * self.tile_x) + ox
        by = (y * self.tile_y) + oy
        self.push_tile (bx, by)
        self.tile_details (x, y)
        self.pop_tile ()
    self.close ()