"""
Example 2. Optimizing vertices.
"""
from __future__ import division
import os
import argparse
import glob

import paddle
import paddle.nn as nn
import numpy as np
from skimage.io import imread, imsave
import tqdm
import imageio

import neural_renderer_paddle as nr

current_dir = os.path.dirname(os.path.realpath(__file__))
data_dir = os.path.join(current_dir, 'data')

class Model(nn.Layer):
    def __init__(self, filename_obj, filename_ref):
        super(Model, self).__init__()

        # load .obj
        vertices, faces = nr.load_obj(filename_obj)
        self.vertices = self.create_parameter(vertices[None, :, :].shape)
        self.vertices.set_value(vertices[None, :, :])
        self.register_buffer('faces', faces[None, :, :])

        # create textures
        texture_size = 2
        textures = paddle.ones([1, self.faces.shape[1], texture_size, texture_size, texture_size, 3], dtype=paddle.float32)
        self.register_buffer('textures', textures)

        # load reference image
        image_ref = paddle.to_tensor(imread(filename_ref).astype(np.float32).mean(-1) / 255.)[None, ::]
        self.register_buffer('image_ref', image_ref)

        # setup renderer
        renderer = nr.Renderer(camera_mode='look_at')
        self.renderer = renderer

    def forward(self):
        self.renderer.eye = nr.get_points_from_angles(2.732, 0, 90)
        image = self.renderer(self.vertices, self.faces, mode='silhouettes')
        loss = paddle.sum((image - self.image_ref[None, :, :])**2)
        return loss


def make_gif(filename):
    with imageio.get_writer(filename, mode='I') as writer:
        for filename in sorted(glob.glob('/tmp/_tmp_*.png')):
            writer.append_data(imageio.imread(filename))
            os.remove(filename)
    writer.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-io', '--filename_obj', type=str, default=os.path.join(data_dir, 'teapot.obj'))
    parser.add_argument('-ir', '--filename_ref', type=str, default=os.path.join(data_dir, 'example2_ref.png'))
    parser.add_argument(
        '-oo', '--filename_output_optimization', type=str, default=os.path.join(data_dir, 'example2_optimization.gif'))
    parser.add_argument(
        '-or', '--filename_output_result', type=str, default=os.path.join(data_dir, 'example2_result.gif'))
    parser.add_argument('-g', '--gpu', type=int, default=0)
    args, _ = parser.parse_known_args()

    model = Model(args.filename_obj, args.filename_ref)

    optimizer = paddle.optimizer.Adam(parameters=filter(lambda p: not p.stop_gradient, model.parameters()))
    # optimizer.setup(model)
    loop = tqdm.tqdm(range(300))
    for i in loop:
        loop.set_description('Optimizing')
        # optimizer.target.cleargrads()
        optimizer.clear_grad()
        loss = model()
        loss.backward()
        optimizer.step()
        images = model.renderer(model.vertices, model.faces, mode='silhouettes')
        image = np.uint8(images.detach().cpu().numpy()[0].clip(0,1)*255)
        imsave('/tmp/_tmp_%04d.png' % i, image)
    make_gif(args.filename_output_optimization)

    # draw object
    loop = tqdm.tqdm(range(0, 360, 4))
    for num, azimuth in enumerate(loop):
        loop.set_description('Drawing')
        with paddle.no_grad():
            model.renderer.eye = nr.get_points_from_angles(2.732, 0, azimuth)
            images, _, _ = model.renderer(model.vertices, model.faces, model.textures)
        image = np.uint8(images.detach().cpu().numpy()[0].transpose((1, 2, 0)).clip(0,1)*255)
        imsave('/tmp/_tmp_%04d.png' % num, image)
    make_gif(args.filename_output_result)


if __name__ == '__main__':
    main()
