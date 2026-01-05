| Command                                                      | Purpose                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------- |
| `sudo docker build ...`                                      | Build RL + ROS simulation image                         |
| `sudo docker run ...`                                        | Run image interactively with GUI & mounted project code |
| `sudo docker exec -it ... bash`                              | Attach additional shell to running container            |
| `apt-get update && apt-get install ...`                      | Fix missing package issues in container                 |
| `pip install ...`                                            | Fix Python dependency issues inside container           |
| `sudo docker system prune -f`                                | Cleanup unused images/containers                        |
| `sudo docker ps`                                             | List running containers                                 |
| `ls /opt/ros/noetic/share/...`                               | Verify presence of launch files or packages             |
| `rostopic echo ...`                                          | Inspect ROS topics in simulation                        |
| `python -m rlrd.ros_bridge`                                  | Run RL agent control bridge                             |
| `sudo docker login`                                          | Authenticate to Docker Hub                              |
| `sudo docker tag rlrd-gazebo gaboreire/rlrd-gazebo:latest`   | Tag your local image for your Docker Hub repo           |
| `sudo docker push gaboreire/rlrd-gazebo:latest`              | Upload (replace) the image in Docker Hub                |
| `sudo docker pull gaboreire/rlrd-gazebo:latest` *(optional)* | Verify the updated image by pulling it                  |

