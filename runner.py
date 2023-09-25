
import os
import time
import random
import argparse
from collections import defaultdict
from prettytable import PrettyTable

import yaml
import traceback
import xerrors
import xerrors.cprint as cp
from xerrors.metrics import confidence_interval

class Runner(object):
    def __init__(self,
                 name="Runner",
                 run_id=None,
                 configuation_index=None,
                 block_configuation=None,):

        self.name = name
        self.run_id = run_id
        self.configuation_index = configuation_index
        self.block_configuation = block_configuation

        self.args = runner_parser()
        self.list = []
        self.runner_list = []
        self.test_list = []

        # skip
        self.skip_name_list = []

    def run(self, func, sort_by_seed=False, **kwargs):

        if self.args.test_mode:
            self.list = self.test_list
        else:
            self.list = self.runner_list

        if len(self.list) == 0:
            cp.warning(self.name, "No configurations found")
            return

        if sort_by_seed:
            self.list = sorted(self.list, key=lambda x: x["seed"] if x.get("seed") else 0)

        self.gpu = self.modified_gpu()

        print(cp.green(f"\nRunning {self.name} with {len(self.list)} configurations", bold=True))
        for config in self.list:
            config = self.refine_config(config)
            print(f" - {config['tag']}" + (f" (@{config['seed']})" if "seed" in config else ""))

        # 确认，开始运行，输入y确认，其余取消
        if not self.args.debug and not self.args.Y:
            option = input("Confirm to run? (y/n): ")
            if option != "y" and option != "Y":
                cp.error(self.name, "Canceled!")
                exit()

        results = []
        for config in self.list:
            result, status = self.execute(func, config, **kwargs)

            if status != "done":
                continue

            print(result["tag"] + " Result:", end=" ")
            cp.print_json(result)
            results.append(result)

        # handle results
        keys = list(results[0].keys())
        keys.remove("tag")
        keys.insert(0, "tag") # tag should be the first column
        result_group = defaultdict(dict)
        for result in results:
            result_group[result["tag"]] = result_group.get(result["tag"], defaultdict(list))
            result_group[result["tag"]]["results"].append(result)

        for group in result_group.values():
            for name in keys:
                if isinstance(group["results"][0].get(name, "N/A"), (int, float)):
                    mean, h = confidence_interval([r[name] for r in group["results"]])
                    group[name] = f"{mean*100:.1f}±{h:.1f}"
                else:
                    group[name] = group["results"][0].get(name, "N/A")
                    if len(group["results"]) > 1:
                        group[name] += f" ({len(group['results'])})"

        cur_time = xerrors.cur_time("human")
        cp.success(self.name, "All Done! " + cur_time)

        # print results
        table = PrettyTable()
        table.field_names = list(keys)
        for tag, group in result_group.items():
            table.add_row([group[name] for name in keys])

        table.align["tag"] = "l"
        print(table)


    def execute(self, func, config, **kwargs):
        print("\n" + "=" * 80)
        print(f"{xerrors.cur_time('human')} Runing: {cp.magenta(config['tag'], bold=True)}")
        print("=" * 80)
        print(config["tag"] + " Config:", end=" ")
        cp.print_json(config)

        result = {}
        status = "start"

        if config["tag"] in self.skip_name_list:
            print(config["tag"], f"Skip! {config['tag']} in skip_name_list")
            status = "skip"
            return result, status

        try:
            result = func(True, **config)
            result["tag"] = config["tag"]
            print(config["tag"], "Done!")
            status = "done"

            # 处理跳过逻辑的代码
            skip_index = kwargs.get("skip_index")
            skip_value = kwargs.get("skip_value")
            if skip_index and skip_value:
                if result.get(skip_index) and result[skip_index] < skip_value:
                    self.skip_name_list.append(config["tag"])
                    print(config["tag"], f"{cp.red('Skip!')} {skip_index}={result[skip_index]} < {skip_value}")
                    status = "skip"


        except KeyboardInterrupt:
            cp.error(self.name, "KeyboardInterrupt: Interrupted by user!")
            status = "interrupted"
            try:
                # time.sleep(3)
                print("10 秒后继续运行", end="")
                for i in range(10, 0, -1):
                    time.sleep(1)
                    print(f"\r{i} 秒后继续运行，使用 Ctrl+C 取消", end="")

            except KeyboardInterrupt:
                cp.error(self.name, "Shutdown by user!")
                exit(-1)

        except Exception as e:
            cp.error(self.name, traceback.format_exc())
            cp.error(self.name, f"Running Error: {e}, Continue...")
            status = "error"

        return result, status


    def add(self, **configs):
        """ Add a new configuration to the runner """
        combinations = self._parse_configuations(configs)
        self.runner_list.extend(combinations)

    def add_test(self, **configs):
        """ Add a new configuration to the runner """
        combinations = self._parse_configuations(configs)
        self.test_list.extend(combinations)

    def _parse_configuations(self, configs):
        """ Depth first search to parse all possible combinations of configurations"""
        if len(configs) == 0:
            return []

        combinations = [{}]
        for key, value in configs.items():
            if isinstance(value, list):
                new_combinations = []
                for item in value:
                    for combination in combinations:
                        new_combinations.append({**combination, key: item})
                combinations = new_combinations
            else:
                for combination in combinations:
                    combination[key] = value

        return combinations

    def refine_config(self, config):
        """ Refine the configuration """
        if self.args.test_mode:
            assert config.get("test_from_ckpt"), "Please specify the checkpoint path for testing"
            if os.path.isdir(config["test_from_ckpt"]):
                config["test_from_ckpt"] = os.path.join(config["test_from_ckpt"], "config.yaml")

            with open(config["test_from_ckpt"], "r") as f:
                ckpt_config = yaml.load(f, Loader=yaml.FullLoader)
                config["tag"] = ckpt_config["tag"]
        else:
            config["tag"] = self.name

        config["gpu"] = config.get("gpu") or self.gpu
        config["tag"] += generate_config_tag(config, self.configuation_index, self.block_configuation)
        config["run_id"] = self.run_id if self.run_id else f"RUN_{xerrors.cur_time()}"

        return config

    def modified_gpu(self):
        if self.args.gpu != "not specified":
            return self.args.gpu
        else:
            return xerrors.get_gpu_by_user_input()


def generate_config_tag(config, configuation_index, block_configuation=None):
    """ Generate a tag for the configuration """
    tag = ""
    for key, value in config.items():

        if key in block_configuation:
            continue

        prefix = configuation_index.get(key, key)
        if value is True:
            tag += f"-{prefix}"
        elif value is False or value is None:
            pass
        else:
            tag += f"-{prefix}#{value}"

    return tag

def runner_parser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-Y", action="store_true", help="Confirm to run")
    parser.add_argument("-T", "--test-mode", action="store_true", help="Run Test")
    parser.add_argument("--gpu", type=str, default="not specified")
    parser.add_argument("--output", type=str, default="output", help="Output directory")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args, _ = parser.parse_known_args()
    return args

def demo_main():
    print("demo_main")
    return {
        "loss": random.random(),
        "acc": random.random(),
    }

if __name__ == "__main__":

    configuation_index = {
        "model": "M",
        "dataset": "D",
        "optimizer": "O-",
    }

    runner = Runner(
        name="Runner",
        run_id="RUN_2021-09-22_21-30-00",
        configuation_index=configuation_index,
    )

    runner.add(
        model=["resnet18", "resnet50"],
        # dataset=["cifar10", "cifar100"],
        optimizer=["sgd", "adam"],
        seed=[1, 2, 3],
    )

    runner.add_test(
        use_thres_val=True,
        test_opt1=["last", "best"],
        batch_size=1,
        test_from_ckpt=["output/ouput-2023-09-20_03-14-22-Kirin-T-R1#start_pos-AttnL#2-MLPL#2", "output/ouput-2023-09-20_05-40-07-Kirin-T-R1#obj-AttnL#2-MLPL#2"],
        # use_thres_threshold=[0.01, 0.001, 0.0005, 0.0001, 0.00001],
        use_thres_threshold=[0.001, 0.0001],
        offline=True,
    )

    runner.run(demo_main)