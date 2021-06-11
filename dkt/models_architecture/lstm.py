from operator import index
from numpy.lib.function_base import select
import torch
import torch.nn as nn
import torch.nn.functional as F 
import numpy as np
import copy
import math
import os

from torch.nn.modules import dropout

from torchsummary import summary


class LSTM(nn.Module):
    
    def __init__(self, args):
        super(LSTM, self).__init__()
        self.args = args
        self.device = args.device

        self.hidden_dim = self.args.hidden_dim
        self.n_layers = self.args.n_layers
        self.cont_cols=1
        #userID때문에 하나 뺌
        cate_len=len(args.cate_feats)-1
        #answerCode 때문에 하나 뺌
        cont_len=len(args.cont_feats)-1
        # cate Embedding 
        self.cate_embedding_list = nn.ModuleList([nn.Linear(max_val+1, (self.hidden_dim//2)//cate_len) for max_val in list(args.cate_feat_dict.values())[1:]]) 
        # cont Embedding
        self.cont_embedding = nn.Linear(1, (self.hidden_dim//2)//cont_len)
        # interaction은 현재 correct로 구성되어있다. correct(1, 2) + padding(0)
        self.embedding_interaction = nn.Embedding(3, (self.hidden_dim//2)//cate_len)
        # self.embedding_test = nn.Embedding(self.args.n_test + 1, self.hidden_dim//3)
        # self.embedding_question = nn.Embedding(self.args.n_questions + 1, self.hidden_dim//3)
        # self.embedding_tag = nn.Embedding(self.args.n_tag + 1, self.hidden_dim//3)
        #shape(batch,msl,feats)
        #continuous
        self.lstm = nn.LSTM(self.hidden_dim,
                            self.hidden_dim,
                            self.n_layers,
                            batch_first=True)
        
        # Fully connected layer
        self.fc = nn.Linear(self.hidden_dim, 1)

        self.activation = nn.Sigmoid()

    def init_hidden(self, batch_size):
        h = torch.zeros(
            self.n_layers,
            batch_size,
            self.hidden_dim)
        h = h.to(self.device)

        c = torch.zeros(
            self.n_layers,
            batch_size,
            self.hidden_dim)
        c = c.to(self.device)

        return (h, c)

    def forward(self, input):
        # cate + cont + interaction + mask + gather_index= input
        print('-'*80)
        print("forward를 시작합니다")
        #userID가 빠졌으므로 -1
        cate_feats=input[:len(self.args.cate_feats)-1]
        print("cate_feats개수",len(cate_feats))
        #answercode가 없으므로 -1
        cont_feats=input[len(self.args.cont_feats)-1:-3]
        print("cont_feats개수",len(cont_feats))      
        interaction=input[-3]
        mask=input[-2]
        gather_index=input[-1]

        batch_size = interaction.size(0)

        # cate Embedding
        cate_feats_embed=[]
        embed_interaction = self.embedding_interaction(interaction)
        cate_feats_embed.append(embed_interaction)

        for i, cate_feat in enumerate(cate_feats): 
            cate_feats_embed.append(self.cate_embedding_list[i](cate_feat))
        

        # unsqueeze cont feats shape
        cont_feats=list(map(unsqueeze(-1),cont_feats))
        # cont Embedding
        cont_feats_embed=[]

        for i, cont_feat in enumerate(cont_feats): 
            cont_feats_embed.append(self.cont_embedding(cont_feat))
        
        #concat cate, cont feats
        embed_cate = torch.cat(cate_feats_embed, 2)
        embed_cont = torch.cat(cont_feats_embed, 2)
        
        X = torch.cat([embed_cate,embed_cont], 2)
        print("cate와 cont를 concat한 shape : ", X.shape)
        
        hidden = self.init_hidden(batch_size)
        out, hidden = self.lstm(X, hidden)
        out = out.contiguous().view(batch_size, -1, self.hidden_dim)

        out = self.fc(out)
        preds = self.activation(out).view(batch_size, -1)

        return preds