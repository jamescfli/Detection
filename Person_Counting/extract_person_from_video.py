import cv2

import time
import numpy as np
import tensorflow as tf

slim = tf.contrib.slim

import sys
sys.path.append('../SSD/')

from SSD.nets import ssd_vgg_512, np_methods
from SSD.preprocessing import ssd_vgg_preprocessing

sess = tf.Session()

net_shape = (512, 1024)     # from origin (1080, 1960)
data_format = 'NCHW'
img_input = tf.placeholder(tf.uint8, shape=(None, None, 3))
image_pre, labels_pre, bboxes_pre, bbox_img = ssd_vgg_preprocessing.preprocess_for_eval(
    img_input, None, None, net_shape, data_format, resize=ssd_vgg_preprocessing.Resize.WARP_RESIZE)
image_4d = tf.expand_dims(image_pre, 0)

reuse = True if 'ssd_net' in locals() else None
ssd_net = ssd_vgg_512.SSDNet()
with slim.arg_scope(ssd_net.arg_scope(data_format=data_format)):
    predictions, localisations, _, _ = ssd_net.net(image_4d, is_training=False, reuse=reuse)

ckpt_filename = '../SSD/checkpoints/VGG_VOC0712_SSD_512x512_ft_iter_120000.ckpt/VGG_VOC0712_SSD_512x512_ft_iter_120000.ckpt'
sess.run(tf.global_variables_initializer())
saver = tf.train.Saver()
saver.restore(sess, ckpt_filename)

ssd_anchors = ssd_net.anchors(net_shape)

def process_image(img, select_threshold=0.5, nms_threshold=.45, net_shape=(300, 300)):
    # Run SSD network.
    rimg, rpredictions, rlocalisations, rbbox_img = sess.run([image_4d, predictions, localisations, bbox_img],
                                                              feed_dict={img_input: img})

    # Get classes and bboxes from the net outputs.
    rclasses, rscores, rbboxes = np_methods.ssd_bboxes_select(
        rpredictions, rlocalisations, ssd_anchors,
        select_threshold=select_threshold, img_shape=net_shape, num_classes=21, decode=True)

    rbboxes = np_methods.bboxes_clip(rbbox_img, rbboxes)
    rclasses, rscores, rbboxes = np_methods.bboxes_sort(rclasses, rscores, rbboxes, top_k=400)
    rclasses, rscores, rbboxes = np_methods.bboxes_nms(rclasses, rscores, rbboxes, nms_threshold=nms_threshold)
    # Resize bboxes to original image shape. Note: useless for Resize.WARP!
    rbboxes = np_methods.bboxes_resize(rbbox_img, rbboxes)
    return rclasses, rscores, rbboxes

# video clip
n_frame_per_min = 510
pesn_cntr_list = []
for hour in np.arange(10,22):
    for minute in np.arange(60):
        print("loading ../datasets/TongYing/20170310/{:02d}/{:02d}.mp4".format(hour, minute))
        cap = cv2.VideoCapture('../datasets/TongYing/20170310/{:02d}/{:02d}.mp4'.format(hour, minute))

        pesn_cntr_list_per_min = []
        while (cap.isOpened()):
            ret, frame = cap.read()
            if ret:
                # resize
                img = cv2.resize(frame, net_shape[::-1], interpolation=cv2.INTER_CUBIC)
                start = time.time()
                rclasses, rscores, rbboxes = process_image(img, net_shape=net_shape)
                end = time.time()
                # print('time elapsed to process one {} img: {}'.format(net_shape, end-start))
                person_counter = 0
                for cls_index in rclasses:
                    if cls_index == 15:
                        person_counter += 1
                pesn_cntr_list_per_min.append(person_counter)
            else:
                break
        if pesn_cntr_list_per_min.__len__() > n_frame_per_min:
            # cut to 510 frames
            pesn_cntr_list_per_min = pesn_cntr_list_per_min[0:n_frame_per_min]
        else:
            pesn_cntr_list_per_min = pesn_cntr_list_per_min + [0] * (n_frame_per_min - pesn_cntr_list_per_min.__len__())
        pesn_cntr_list.append(pesn_cntr_list_per_min)

cap.release()
cv2.destroyAllWindows()

np.savetxt('outputs/person_counter.txt', np.array(pesn_cntr_list), fmt='%d', delimiter=',')
