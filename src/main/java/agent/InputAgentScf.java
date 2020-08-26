/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package agent;

import java.io.IOException;
import java.util.ArrayList;

import app.input.geo.Element;
import core.agent.InputAgent;
import core.agent.WrapperBoolean;
import core.agent.WrapperDouble;
import core.agent.WrapperEnum;
import core.agent.WrapperInteger;

import com.consts.Constants.EnumHybridFunc;
import com.consts.Constants.EnumHybridTreat;
import com.consts.Constants.EnumMixingMode;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumUnitEnergy;
import com.consts.Constants.EnumVdw;

public class InputAgentScf extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3659165710616979269L;
	
	public Boolean setMag,
	setU,
	setHybrid,
	setVdw,
	setAdv,
	setE;
	public Boolean expandStandard,
	expandMag,
	expandU,
	expandHybrid,
	expandVdw,
	expandAdv,
	expandE;
	
	//standard
	public WrapperEnum enumOccupation;//EnumOccupations 
	public WrapperBoolean boolRestart;
	public WrapperBoolean boolForce;
	public WrapperBoolean boolStress;
	public WrapperEnum enumEnergyUnit;
	public WrapperDouble  ecutWfc,
	ecutRho,
	elecConv,
	mixBeta,
	degauss;
	public WrapperInteger nElecMaxStep,
	nkx,
	nky,
	nkz;
	public WrapperBoolean boolKGamma;
	
	public WrapperEnum enumMixing;//EnumMixingMode
	public WrapperEnum enumSmearing;//EnumSmearing
	
	//magnet
	public WrapperInteger nspin;
	public WrapperBoolean noncolin;
	public WrapperBoolean boolSoc;
	public WrapperBoolean setForElements;
	public WrapperBoolean setForAtoms;
	//hubbardU
	//public WrapperBoolean boolHubbardU;
	public WrapperBoolean lda_plus_u;
	public ArrayList<Element> elementList;
	
	//hybrid
	public WrapperEnum enumHybrid;
	public WrapperEnum enumTreat;
	public WrapperDouble ecutvcut;
	public WrapperBoolean xgammaextrap;
	public WrapperInteger nqx,
	nqy,
	nqz;
	
	//vdw
	public WrapperEnum enumVdw;
	
	//for compatibility 
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for loading after serialization
	    in.defaultReadObject();
	    //account for version difference in loading parameters
	    if(boolKGamma==null) {boolKGamma = new WrapperBoolean(false);}
	    
	    //hybrid, added in v0.2.0
	    if(enumHybrid==null) {enumHybrid = new WrapperEnum(EnumHybridFunc.defaultFunctional);}
	    if(enumTreat==null) {enumTreat = new WrapperEnum(EnumHybridTreat.gb);}
	    if(ecutvcut==null) {ecutvcut = new WrapperDouble(0.0);}
	    if(xgammaextrap==null) {xgammaextrap = new WrapperBoolean(true);}
	    if(nqx==null) {nqx = new WrapperInteger(1);}
	    if(nqy==null) {nqy = new WrapperInteger(1);}
	    if(nqz==null) {nqz = new WrapperInteger(1);}
	    
	    //vdw, added in v0.2.0
	    if(enumVdw==null) {enumVdw = new WrapperEnum(EnumVdw.no);}
	}
	
	public InputAgentScf() {
		//************************|***********//
		//***********************\|/**********//
		//*******already dealt with in PwInput//
		//general
		setMag=false;setU=false;setHybrid=false;
		setVdw=false;setAdv=false;setE=false;
		expandStandard=false;expandMag=false;expandU=false;expandHybrid=false;
		expandVdw=false;expandAdv=false;expandE=false;
		//spin
		nspin=new WrapperInteger(1);noncolin=new WrapperBoolean(false);boolSoc=new WrapperBoolean(false);//ok
		setForElements=new WrapperBoolean(false);//ok
		setForAtoms = new WrapperBoolean(false);//ok
		//DFT+U
		//boolHubbardU=new WrapperBoolean(false);
		lda_plus_u=new WrapperBoolean(false);//ok
		elementList = new ArrayList<Element>();//ok, //for scfHubbard, part of all elements
		//standard
		boolRestart=new WrapperBoolean(false); //false is from scratch //ok
		boolForce=new WrapperBoolean(false);boolStress=new WrapperBoolean(false);
		enumOccupation=new WrapperEnum(EnumOccupations.smearing,true);//ok, not QE default
		enumEnergyUnit = new WrapperEnum(EnumUnitEnergy.Ry,true);//ok, not QE default
		ecutWfc = new WrapperDouble(30.0);//ok
		ecutRho = new WrapperDouble(120.0);//ok
		nElecMaxStep=new WrapperInteger(100);elecConv=new WrapperDouble(1e-6);enumMixing=new WrapperEnum(EnumMixingMode.plain);
		mixBeta=new WrapperDouble(0.7);//ok
		nkx = new WrapperInteger(4);//ok
		nky = new WrapperInteger(4);//ok
		nkz = new WrapperInteger(4);//ok
		boolKGamma = new WrapperBoolean(false);
		enumSmearing=new WrapperEnum(EnumSmearing.gauss);//ok
		degauss = new WrapperDouble(0.02);//ok
		//***********************/|\*********//
		//************************|**********//
		
		//hybrid functional
		enumHybrid = new WrapperEnum(EnumHybridFunc.defaultFunctional);
		enumTreat = new WrapperEnum(EnumHybridTreat.gb);
		ecutvcut = new WrapperDouble(0.0);
		xgammaextrap = new WrapperBoolean(true);
		nqx = new WrapperInteger(1);
		nqy = new WrapperInteger(1);
		nqz = new WrapperInteger(1);
		
		//vdw
		enumVdw = new WrapperEnum(EnumVdw.no);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		// TODO Auto-generated method stub
		return false;
	}
}
