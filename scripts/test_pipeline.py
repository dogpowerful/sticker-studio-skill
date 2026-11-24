"""Synthetic variation tests; no model calls or character-specific assets."""
import unittest
from PIL import Image, ImageDraw
from sticker_pipeline import stabilize_labels, torso_center_x, fit_full_body


def moving_character():
    frames=[]
    for shift in [-24,-18,-12,-6,0,6,12,18,24]:
        f=Image.new('RGBA',(418,418));d=ImageDraw.Draw(f)
        # White hardhat, orange torso and red floating seal.
        d.rectangle((150+shift,90,250+shift,135),fill='white')
        d.rectangle((155+shift,140,245+shift,350),fill='orange')
        d.rectangle((310,12,370,70),fill='red')
        frames.append(f)
    return frames


class PipelineVariations(unittest.TestCase):
    def test_none_keeps_intended_dance_translation_and_colored_seal(self):
        frames=stabilize_labels(moving_character(),align='none',label_mode='none')
        centers=[torso_center_x(f) for f in frames]
        self.assertGreater(max(centers)-min(centers),30)
        colors=[frames[0].getpixel((x,y)) for y in range(418) for x in range(418)
                if frames[0].getpixel((x,y))[3]>=145]
        self.assertTrue(any(r>200 and g<40 and b<40 for r,g,b,a in colors))
        self.assertTrue(any(min(r,g,b)>240 for r,g,b,a in colors))

    def test_manual_anchors_remove_translation_without_white_panel(self):
        anchors=[(200+x)/418 for x in [-24,-18,-12,-6,0,6,12,18,24]]
        frames=stabilize_labels(moving_character(),align='manual',anchors=anchors,label_mode='none')
        centers=[torso_center_x(f) for f in frames]
        self.assertLessEqual(max(centers)-min(centers),1)

    def test_full_body_fit_does_not_flush_broad_feet_to_edge(self):
        frames=fit_full_body(moving_character(),240,6)
        for f in frames:
            box=f.getchannel('A').point(lambda a:255 if a>=145 else 0).getbbox()
            self.assertGreaterEqual(min(box[0],box[1],240-box[2],240-box[3]),6)


if __name__=='__main__':unittest.main()
