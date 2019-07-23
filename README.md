Image browser
-------------

Prototype for non-verbal access to information, targeting users with intellectual disability.
This prototype shows a UI which allows browsing a large database of images. At each stage,
the demo shows a target image at the center and thumbnails of images similar to that image
around it. There are several combinations of image selection and sorting algorithms:
- closest in term of similarity
- diverse using an MMR-like algorithm
- 1d sorting, top-left is most similar
- 2d sorting, close-together images are most similar

The algorithm uses image representations generated with a deep convolutional neural network such as ResNet.

### Running

To run, make sure you have python3 accessible as python, virtualenv and gcc installed. 

```shell
./run.sh
```

### Format for data

This prototype can accomodate for multiple data sources. Each data directory shall conain:
- `images/` a directory with thumbnails
- `names.txt` a file containing am image thumbanil filename and a source image path separated by a tab on each line
- `vectors.npy` a numpy matrix of shape number of images times dimension of representation where each row corresponds to the image on the same row in `names.txt`

Representations are typically low-dimension dense vectors (for example size 256) and can be generated with CNNs such as ResNet. 
